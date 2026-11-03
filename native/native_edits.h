// Native SDK edits dispatched on the editor thread. No input injection, editor
// subclassing, executable patches, offsets or undocumented Qt calls.
struct NativeJob {
    json request,result;
    HANDLE done=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    uint64_t deadline=GetTickCount64()+3000;
    ~NativeJob(){if(done)CloseHandle(done);}
};
static std::mutex jobLock;
static std::deque<std::shared_ptr<NativeJob>> jobs;
struct EditPlan {json ops;std::string revision,approval; qWorld_t* world;uint64_t expires;};
static std::map<std::string,EditPlan> plans;
static fs::path boundFile;
static std::string boundCaption;
static bool fixtureEdits=false;

static void onEditorThread(){
    if(GetCurrentThreadId()!=editorThread)throw std::runtime_error("Editor-thread guard");
}
static std::vector<qEntity_t*> entitiesIn(qWorld_t* world){
    qWorld_t w{};if(!readValue(world,w))throw std::runtime_error("No readable document");
    std::vector<qEntity_t*> out;std::set<qEntity_t*> seen;
    for(auto p=w.m_entityList;p;){
        qEntity_t e{};
        if(out.size()>=8192||!seen.insert(p).second||!readValue(p,e)||e.m_ownerWorld!=world)
            throw std::runtime_error("Invalid entity chain");
        out.push_back(p);p=e.next;
    }
    return out;
}
static qEntity_t* entityById(qWorld_t* world,int id){
    for(auto p:entitiesIn(world))if(p->m_editorId==id)return p;
    throw std::runtime_error("Entity ID not in current document");
}
static qBrush_t* brushById(qWorld_t* world,int id){
    std::set<qBrush_t*> seen;
    for(auto e:entitiesIn(world))for(auto p=e->m_brushList;p;){
        qBrush_t b{};
        if(seen.size()>=32768||!seen.insert(p).second||!readValue(p,b)||b.m_ownerEntity!=e)
            throw std::runtime_error("Invalid brush chain");
        if(b.m_editorId==id)return p;p=b.next;
    }
    throw std::runtime_error("Brush ID not in current document");
}
static json entityProps(const qEntity_t& e){
    json props=json::object();std::set<epair_t*> seen;
    for(auto p=e.epairs;p;){
        epair_t pair{};
        if(seen.size()>=128||!seen.insert(p).second||!readValue(p,pair))throw std::runtime_error("Invalid properties");
        props[text(pair.key)]=text(pair.value);p=pair.next;
    }
    return props;
}
static std::vector<qFace_t*> facesIn(qBrush_t* brush){
    std::vector<qFace_t*> out;std::set<qFace_t*> seen;
    for(auto p=brush->m_faceList;p;){
        qFace_t f{};
        if(out.size()>=256||!seen.insert(p).second||!readValue(p,f)||f.m_ownerBrush!=brush||f.m_vertexCount<3||f.m_vertexCount>256)
            throw std::runtime_error("Invalid brush face");
        out.push_back(p);p=f.next;
    }
    if(out.size()<4)throw std::runtime_error("Brush has fewer than four faces");
    return out;
}
static json fullState(qWorld_t* world){
    // Includes all objects/vertices/textures/properties, excluding selection and
    // transient renderer state. Recovery JSON is not a full-fidelity JMF serializer.
    json out=json::array();size_t brushCount=0,vertexCount=0;
    for(auto e:entitiesIn(world)){
        json bs=json::array();std::set<qBrush_t*> seen;
        for(auto b=e->m_brushList;b;b=b->next){
            if(++brushCount>32768||!seen.insert(b).second)throw std::runtime_error("Brush limit/cycle");
            json fsj=json::array();
            for(auto f:facesIn(b)){
                json vs=json::array();
                for(int i=0;i<f->m_vertexCount;++i){
                    qVertex_t v{};if(++vertexCount>1000000||!readValue(f->m_vertices+i,v))throw std::runtime_error("Invalid vertex data");
                    vs.push_back({{"coords",vector3(v.coords)},{"uv",vector3(v.uv)}});
                }
                fsj.push_back({{"vertices",vs},{"texdef_bytes",hex((const unsigned char*)&f->m_texDef,sizeof(f->m_texDef))}});
            }
            bs.push_back({{"id",b->m_editorId},{"flags",b->m_editorFlags&~(EFL_SELECTED|EFL_DIRTY)},
                {"faces",fsj}});
        }
        out.push_back({{"id",e->m_editorId},{"classname",text(e->m_className)},
            {"origin",vector3(e->m_vecOrigin)},{"angles",vector3(e->m_vecAngles)},
            {"flags",e->m_editorFlags&~(EFL_SELECTED|EFL_DIRTY)},
            {"properties",entityProps(*e)},{"brushes",bs}});
    }
    if(out.dump().size()>64*1024*1024)throw std::runtime_error("Recovery snapshot above 64 MiB");
    return out;
}
static vec3_t jsonVector(const json& a){
    if(!a.is_array()||a.size()!=3)throw std::runtime_error("Expected XYZ array");
    vec3_t v{};for(int i=0;i<3;++i){v[i]=a[i].get<float>();if(!std::isfinite(v[i])||fabs(v[i])>30000)throw std::runtime_error("Coordinate outside supported edit bounds");}
    return v;
}
static std::string asciiField(const json& v,size_t max){
    auto s=v.get<std::string>();if(s.empty()||s.size()>max)throw std::runtime_error("Invalid text length");
    for(unsigned char c:s)if(c<32||c>126||c=='"'||c=='\\')throw std::runtime_error("Use printable ASCII without quotes/backslashes");
    return s;
}
static HWND editorRoot(){
    HWND found=nullptr;
    EnumThreadWindows(editorThread,[](HWND h,LPARAM p)->BOOL{
        wchar_t title[512]{};GetWindowTextW(h,title,512);
        if(IsWindowVisible(h)&&wcsstr(title,L"J.A.C.K.")) {*(HWND*)p=h;return FALSE;}return TRUE;
    },(LPARAM)&found);return found;
}
static void documentGuard(){
    HWND root=editorRoot();if(!root||!IsWindowEnabled(root))throw std::runtime_error("Editor unavailable or modal dialog open");
    wchar_t title[1024]{};GetWindowTextW(root,title,1024);
    std::wstring caption=fs::path(boundFile).filename().wstring();
    if(caption.empty()||!wcsstr(title,caption.c_str()))throw std::runtime_error("Active document title does not match bound working file; maximize that map");
    // Prevent edits during a foreground modal owned by the same editor.
    HWND active=GetActiveWindow();if(active&&GetAncestor(active,GA_ROOT)!=root)throw std::runtime_error("Editor has an active modal/popup");
}
static void validateOps(qWorld_t* world,const json& ops){
    if(!ops.is_array()||ops.empty()||ops.size()>16)throw std::runtime_error("Use 1 to 16 operations per plan");
    for(const auto& op:ops){
        auto kind=op.at("op").get<std::string>();
        if(kind=="create_brush"){
            auto lo=jsonVector(op.at("min")),hi=jsonVector(op.at("max"));
            for(int i=0;i<3;++i)if(hi[i]-lo[i]<1||hi[i]-lo[i]>8192)throw std::runtime_error("Brush dimensions must be 1..8192 units");
            asciiField(op.at("texture"),63);
        }else if(kind=="duplicate_brush"||kind=="move_brush"||kind=="rotate_brush_z"){
            auto b=brushById(world,op.at("brush_id").get<int>());
            if(text(b->m_ownerEntity->m_className)!="worldspawn")throw std::runtime_error("Brush transforms currently support world brushes only");
            facesIn(b);
            if(kind=="rotate_brush_z"){
                jsonVector(op.at("pivot"));float deg=op.at("degrees").get<float>();
                if(!std::isfinite(deg)||fabs(deg)>360)throw std::runtime_error("Rotation must be -360..360 degrees");
            }else jsonVector(op.at("delta"));
        }else if(kind=="create_entity"){
            auto name=asciiField(op.at("classname"),63);jsonVector(op.at("origin"));
            if(name!="info_target"&&name!="light"&&name!="info_player_start"&&name!="info_player_deathmatch")throw std::runtime_error("Point classname not yet validated for native creation");
        }else if(kind=="move_entity"||kind=="set_entity_property"){
            auto e=entityById(world,op.at("entity_id").get<int>());
            if(e->m_brushList||text(e->m_className)=="worldspawn")throw std::runtime_error("Only point entities are supported by this operation");
            if(kind=="move_entity")jsonVector(op.at("delta"));
            else{
                auto key=asciiField(op.at("key"),63);asciiField(op.at("value"),1024);
                if(key=="classname"||key=="origin"||key=="angles"||key=="mapversion"||key=="wad")throw std::runtime_error("Reserved property; use dedicated operation");
            }
        }else throw std::runtime_error("Unsupported native edit operation");
    }
}
static void setPair(qEntity_t* e,const std::string& key,const std::string& value){
    auto& a=api;epair_t* last=nullptr;
    for(auto p=e->epairs;p;p=p->next){
        if(text(p->key)==key){
            auto newValue=a.pfnSys_AllocString(value.c_str());if(!newValue)throw std::runtime_error("Editor allocation failed");
            a.pfnSys_Free(p->value);p->value=newValue;return;
        }last=p;
    }
    auto pair=(epair_t*)a.pfnSys_Malloc(sizeof(epair_t));if(!pair)throw std::runtime_error("Editor allocation failed");
    pair->next=nullptr;pair->key=a.pfnSys_AllocString(key.c_str());pair->value=a.pfnSys_AllocString(value.c_str());
    if(!pair->key||!pair->value)throw std::runtime_error("Editor string allocation failed");
    if(last)last->next=pair;else e->epairs=pair;
}
static qBrush_t* newBox(qWorld_t* world,const vec3_t& lo,const vec3_t& hi,const std::string& texture){
    auto owner=entitiesIn(world).at(0);
    if(text(owner->m_className)!="worldspawn")throw std::runtime_error("Worldspawn missing");
    vec3_t v[8]={{lo.x,lo.y,lo.z},{lo.x,lo.y,hi.z},{lo.x,hi.y,lo.z},{lo.x,hi.y,hi.z},
        {hi.x,hi.y,lo.z},{hi.x,hi.y,hi.z},{hi.x,lo.y,lo.z},{hi.x,lo.y,hi.z}};
    static const int table[6][4]={{0,1,3,2},{2,3,5,4},{4,5,7,6},{6,7,1,0},{1,7,5,3},{0,2,4,6}};
    auto b=api.brushfuncs.pfnBrush_Create(world,owner);if(!b)throw std::runtime_error("Brush allocation failed");
    try{
        for(int i=0;i<6;++i){
            qTexDef_t t{};strncpy_s(t.m_textureName,texture.c_str(),63);
            t.m_scale={1,1};t.m_textureAlignment=TEXALIGN_QUAKE;
            auto f=api.facefuncs.pfnFace_Create(world,b,&t,4);if(!f)throw std::runtime_error("Face allocation failed");
            for(int j=0;j<4;++j)f->m_vertices[j].coords=v[table[i][j]];
            PlaneFromPoints(f->m_vertices[0].coords,f->m_vertices[1].coords,f->m_vertices[2].coords,f->m_plane);
        }
        api.entityfuncs.pfnEntity_Build(owner,ENT_BLDFLG_BIT1|ENT_BLDFLG_BIT3);
    }catch(...){api.brushfuncs.pfnBrush_Destroy(world,b);throw;}
    return b;
}
static void updateBrushBounds(qBrush_t* b){
    bool firstBrush=true;
    for(auto f:facesIn(b)){
        for(int i=0;i<f->m_vertexCount;++i){
            const auto& p=f->m_vertices[i].coords;
            if(i==0){f->m_bboxMin=p;f->m_bboxMax=p;}
            else for(int a=0;a<3;++a){f->m_bboxMin[a]=std::min(f->m_bboxMin[a],p[a]);f->m_bboxMax[a]=std::max(f->m_bboxMax[a],p[a]);}
            if(firstBrush){b->m_bboxMin=p;b->m_bboxMax=p;firstBrush=false;}
            else for(int a=0;a<3;++a){b->m_bboxMin[a]=std::min(b->m_bboxMin[a],p[a]);b->m_bboxMax[a]=std::max(b->m_bboxMax[a],p[a]);}
        }
        f->m_editorFlags|=EFL_DIRTY;
    }
    b->m_editorFlags|=EFL_DIRTY;
    auto owner=b->m_ownerEntity;bool firstEntity=true;
    for(auto p=owner->m_brushList;p;p=p->next){
        if(firstEntity){owner->m_bboxMin=p->m_bboxMin;owner->m_bboxMax=p->m_bboxMax;firstEntity=false;}
        else for(int a=0;a<3;++a){owner->m_bboxMin[a]=std::min(owner->m_bboxMin[a],p->m_bboxMin[a]);owner->m_bboxMax[a]=std::max(owner->m_bboxMax[a],p->m_bboxMax[a]);}
    }
}
static json performOps(qWorld_t* world,const json& ops){
    json ids=json::array();
    api.undofuncs.pfnUndo_Start(world,"Codex native edit");
    try{
        for(const auto& op:ops){
            auto kind=op.at("op").get<std::string>();
            if(kind=="create_brush"){
                auto b=newBox(world,jsonVector(op["min"]),jsonVector(op["max"]),op["texture"]);
                api.undofuncs.pfnUndo_AddBrush(b);ids.push_back({{"type","brush"},{"id",b->m_editorId}});
            }else if(kind=="move_brush"||kind=="rotate_brush_z"||kind=="duplicate_brush"){
                auto source=brushById(world,op["brush_id"]);auto b=source;
                if(kind=="duplicate_brush"){
                    b=api.brushfuncs.pfnBrush_Create(world,source->m_ownerEntity);
                    if(!b)throw std::runtime_error("Brush allocation failed");
                    for(auto f:facesIn(source)){
                        auto copy=api.facefuncs.pfnFace_Create(world,b,&f->m_texDef,f->m_vertexCount);
                        if(!copy)throw std::runtime_error("Face allocation failed");
                        for(int i=0;i<f->m_vertexCount;++i)copy->m_vertices[i]=f->m_vertices[i];
                    }
                }else api.undofuncs.pfnUndo_StoreBrush(b);
                const bool rotate=kind=="rotate_brush_z";
                auto vec=jsonVector(op.at(rotate?"pivot":"delta"));float c=1,s=0;
                if(rotate){float rad=op["degrees"].get<float>()*3.14159265359f/180;c=cosf(rad);s=sinf(rad);}
                for(auto f:facesIn(b)){
                for(int i=0;i<f->m_vertexCount;++i){
                    auto& p=f->m_vertices[i].coords;
                    if(rotate){float x=p.x-vec.x,y=p.y-vec.y;p.x=vec.x+x*c-y*s;p.y=vec.y+x*s+y*c;}
                    else p+=vec;
                }
                PlaneFromPoints(f->m_vertices[0].coords,f->m_vertices[1].coords,f->m_vertices[2].coords,f->m_plane);
                }
                updateBrushBounds(b);
                api.entityfuncs.pfnEntity_Build(b->m_ownerEntity,ENT_BLDFLG_BIT1|ENT_BLDFLG_BIT3);
                updateBrushBounds(b);
                if(kind=="duplicate_brush")api.undofuncs.pfnUndo_AddBrush(b);
                ids.push_back({{"type","brush"},{"id",b->m_editorId}});
            }else if(kind=="create_entity"){
                auto origin=jsonVector(op["origin"]);std::string classname=op["classname"];
                auto e=api.entityfuncs.pfnEntity_Create(world,classname.c_str(),origin.Base(),0);
                if(!e)throw std::runtime_error("Entity allocation failed");
                api.undofuncs.pfnUndo_AddEntity(e);
                api.entityfuncs.pfnEntity_Build(e,ENT_BLDFLG_FULLBUILD);
                ids.push_back({{"type","entity"},{"id",e->m_editorId}});
            }else{
                auto e=entityById(world,op["entity_id"]);api.undofuncs.pfnUndo_StoreEntity(e);
                if(kind=="move_entity")e->m_vecOrigin+=jsonVector(op["delta"]);
                else setPair(e,op["key"],op["value"]);
                api.entityfuncs.pfnEntity_Build(e,ENT_BLDFLG_FULLBUILD);
                ids.push_back({{"type","entity"},{"id",e->m_editorId}});
            }
        }
        api.undofuncs.pfnUndo_End(world);
        world->m_editorFlags|=EFL_DIRTY;
        HWND root=editorRoot();if(root)RedrawWindow(root,nullptr,nullptr,RDW_INVALIDATE|RDW_ALLCHILDREN);
    }catch(...){api.undofuncs.pfnUndo_End(world);editFaulted=true;throw;}
    return ids;
}
static json handleEditorRequest(const json& q){
    onEditorThread();const std::string method=q.at("method");
    if(method=="snapshot"){
        refresh(0);std::lock_guard<std::mutex> g(lockSnapshot);auto r=snapshot;
        if(r.contains("captured_tick_ms"))r["age_ms"]=GetTickCount64()-r["captured_tick_ms"].get<uint64_t>();
        return r;
    }
    if(!editEnabled||editFaulted)throw std::runtime_error("Native edits disabled or faulted for this session");
    documentGuard();auto world=api.pfnGlobal_GetCurrentWorld();
    if(!world)throw std::runtime_error("No active document");
    if(method=="plan_edits"){
        auto ops=q.at("params").at("operations");validateOps(world,ops);
        auto state=fullState(world);auto revision=digest(state.dump());
        std::string id=randomHex(16),approval=randomHex(24);
        plans.clear();plans.emplace(id,EditPlan{ops,revision,approval,world,GetTickCount64()+300000});
        return {{"ok",true},{"plan_id",id},{"approval_token",approval},{"operations",ops},
            {"revision",revision},{"expires_in_seconds",300},{"requires_user_approval",true},
            {"bound_file_hint",boundFile.u8string()},{"save_as_required",true},
            {"warning","EXPERIMENTAL: host unsaved-change notification is not reliable. File > Save As JMF after edits; do not close based on absence of a star."},
            {"checkpoint_scope","saved source plus full SDK geometry/property recovery JSON; not full JMF metadata"}};
    }
    auto params=q.at("params");auto id=params.at("plan_id").get<std::string>();auto it=plans.find(id);
    if(it==plans.end())throw std::runtime_error("Unknown/consumed plan");
    auto plan=it->second;
    if(params.at("approval_token")!=plan.approval)throw std::runtime_error("Approval token does not match this exact plan");
    plans.erase(it); // single use, even when stale; never replay after a timeout
    if(GetTickCount64()>plan.expires||world!=plan.world)throw std::runtime_error("Plan expired or document changed");
    auto before=fullState(world);if(digest(before.dump())!=plan.revision)throw std::runtime_error("Document changed since preview; make a new plan");
    validateOps(world,plan.ops);
    fs::path dir=dataDir/L"recovery"/fs::u8path(id);fs::create_directories(dir);
    {std::ofstream f(dir/L"before-sdk.json");f<<before.dump(2);if(!f)throw std::runtime_error("Recovery checkpoint write failed");}
    if(!fs::is_regular_file(boundFile))throw std::runtime_error("Bound saved map missing");
    fs::copy_file(boundFile,dir/boundFile.filename(),fs::copy_options::none);
    logEvent("edit_begin",id);
    json ids;
    try{ids=performOps(world,plan.ops);}catch(...){logEvent("edit_fault",id);throw;}
    auto after=fullState(world);auto revision=digest(after.dump());
    if(revision==plan.revision){editFaulted=true;throw std::runtime_error("No verified state change; session locked");}
    {std::ofstream f(dir/L"after-sdk.json");f<<after.dump(2);}
    auto result=json{{"ok",true},{"plan_id",id},{"changed_objects",ids},{"revision_before",plan.revision},
        {"revision_after",revision},{"recovery_directory",dir.u8string()},{"undo_transaction",true},
        {"saved",false},{"save_as_required",true},{"note","EXPERIMENTAL: changed in editor memory. Use File > Save As JMF; host unsaved-change prompt is unreliable. Native Undo invocation is not exposed by the SDK."}};
    {std::ofstream f(dir/L"receipt.json");f<<result.dump(2);}
    logEvent("edit_verified",id);refresh(0);return result;
}
static LRESULT CALLBACK dispatcherProc(HWND h,UINT msg,WPARAM w,LPARAM l){
    if(msg==WM_APP+51){
        std::shared_ptr<NativeJob> job;
        {std::lock_guard<std::mutex> g(jobLock);if(!jobs.empty()){job=jobs.front();jobs.pop_front();}}
        if(job){
            try{
                if(GetTickCount64()>job->deadline)throw std::runtime_error("Request expired before execution; no action taken");
                job->result=handleEditorRequest(job->request);
            }catch(const std::exception& e){job->result={{"ok",false},{"error",e.what()},{"faulted",editFaulted.load()}};logEvent("native_request_error",e.what());}
            SetEvent(job->done);
        }
        return 0;
    }
    return DefWindowProcW(h,msg,w,l);
}
static json dispatchRequest(const json& q){
    if(!dispatchWindow)throw std::runtime_error("Editor dispatcher unavailable");
    auto job=std::make_shared<NativeJob>();job->request=q;
    if(!job->done)throw std::runtime_error("Cannot create request event");
    {std::lock_guard<std::mutex> g(jobLock);if(jobs.size()>=8)throw std::runtime_error("Native queue full");jobs.push_back(job);}
    if(!PostMessageW(dispatchWindow,WM_APP+51,0,0))throw std::runtime_error("Cannot dispatch to editor thread");
    if(WaitForSingleObject(job->done,3500)!=WAIT_OBJECT_0)
        return {{"ok",false},{"error","Editor did not finish before timeout; do not replay apply. Inspect audit/recovery and current state."},{"outcome_unknown",true}};
    return job->result;
}
static bool setupDispatcher(HMODULE module){
    WNDCLASSW wc{};wc.lpfnWndProc=dispatcherProc;wc.hInstance=module;wc.lpszClassName=L"JACKCodexNativeDispatcher";
    if(!RegisterClassW(&wc)&&GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)return false;
    dispatchWindow=CreateWindowExW(0,wc.lpszClassName,L"",0,0,0,0,0,HWND_MESSAGE,nullptr,module,nullptr);
    if(!dispatchWindow)return false;
    auto config=dataDir.parent_path()/L"codex-edit-session.json";
    if(fs::is_regular_file(config)){
        auto c=json::parse(fileBytes(config));boundFile=fs::u8path(c.at("working_file").get<std::string>());
        fixtureEdits=c.value("test_fixture",false);
        // Session staging may enable native edits only for a bound saved copy.
        editEnabled=c.value("enabled",false)&&fs::is_regular_file(boundFile)&&
            api.pfnSys_Malloc&&api.pfnSys_Free&&api.pfnSys_AllocString&&
            api.entityfuncs.pfnEntity_Create&&api.entityfuncs.pfnEntity_Build&&
            api.brushfuncs.pfnBrush_Create&&api.brushfuncs.pfnBrush_Destroy&&api.facefuncs.pfnFace_Create&&
            api.undofuncs.pfnUndo_Start&&api.undofuncs.pfnUndo_End&&api.undofuncs.pfnUndo_AddBrush&&
            api.undofuncs.pfnUndo_StoreBrush&&api.undofuncs.pfnUndo_AddEntity&&api.undofuncs.pfnUndo_StoreEntity;
    }
    return true;
}
