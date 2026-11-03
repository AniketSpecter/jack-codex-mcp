// Experimental process-lifetime native bridge; SDK calls run on the UI thread.
#include <windows.h>
#include <sddl.h>
#include <bcrypt.h>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <set>
#include <string>
#include <vector>
#include <deque>
#include <memory>
#include <atomic>
#include "PluginAPI.h"
#include "PluginActions.h"
#include "PluginEntity.h"
#include "PluginWorld.h"
#include "json.hpp"

using json = nlohmann::json;
namespace fs = std::filesystem;
static plugin_funcs_t api{};
static bool ready = false;
static DWORD editorThread = 0;
static std::mutex lockSnapshot;
static json snapshot;
static fs::path dataDir;
static std::string token, sessionId, versionString;
static std::wstring pipeName;
static PSECURITY_DESCRIPTOR descriptor = nullptr;
static uint64_t generation = 0;
static HWND dispatchWindow=nullptr;
static bool editEnabled=false;
static std::atomic<bool> editFaulted{false};
constexpr DWORD MAX_MESSAGE = 256 * 1024;
constexpr char EXE_SHA[] = "1dcd13dbc6ded7181ae47b611a11f6c08c8e2da85af14f03c4ca9bc705bfdac8";

// SEH contains invalid SDK pointers in this experimental read-only probe.
template<class T> static bool readValue(const T* p, T& out) {
    if (!p) return false;
    __try { memcpy(&out, p, sizeof(T)); return true; }
    __except(EXCEPTION_EXECUTE_HANDLER) { return false; }
}
static bool readStringRaw(const char* p, char* out, size_t cap) {
    if (!p) {out[0]=0; return true;}
    __try {
        for (size_t i=0; i<cap; ++i) {
            out[i] = p[i]; if (!out[i]) return true;
        }
        return false;
    } __except(EXCEPTION_EXECUTE_HANDLER) {return false;}
}
static std::string text(const char* p) {
    char b[2049]{};
    if (!readStringRaw(p,b,sizeof(b))) throw std::runtime_error("Invalid/oversized SDK string");
    // SDK text is local ANSI. Normalize to UTF-8 for MCP rather than assuming UTF-8.
    int n=MultiByteToWideChar(CP_ACP,0,b,-1,nullptr,0);
    std::wstring w(n,0); MultiByteToWideChar(CP_ACP,0,b,-1,w.data(),n);
    n=WideCharToMultiByte(CP_UTF8,0,w.c_str(),-1,nullptr,0,nullptr,nullptr);
    std::string s(n,0); WideCharToMultiByte(CP_UTF8,0,w.c_str(),-1,s.data(),n,nullptr,nullptr);
    s.resize(s.size()-1); return s;
}
static std::string hex(const unsigned char* b,size_t n) {
    const char* h="0123456789abcdef"; std::string s; s.reserve(n*2);
    for(size_t i=0;i<n;++i) {s+=h[b[i]>>4];s+=h[b[i]&15];} return s;
}
static std::string digest(const std::string& bytes) {
    BCRYPT_ALG_HANDLE alg=nullptr; BCRYPT_HASH_HANDLE hash=nullptr;
    unsigned char result[32]{};
    if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0) throw std::runtime_error("SHA provider failed");
    NTSTATUS s=BCryptCreateHash(alg,&hash,nullptr,0,nullptr,0,0);
    if(s>=0) s=BCryptHashData(hash,(PUCHAR)bytes.data(),(ULONG)bytes.size(),0);
    if(s>=0) s=BCryptFinishHash(hash,result,sizeof(result),0);
    if(hash) BCryptDestroyHash(hash); BCryptCloseAlgorithmProvider(alg,0);
    if(s<0) throw std::runtime_error("SHA failed"); return hex(result,sizeof(result));
}
static std::string fileBytes(const fs::path& p) {
    std::ifstream f(p,std::ios::binary); if(!f) throw std::runtime_error("Cannot read probe file");
    return std::string(std::istreambuf_iterator<char>(f),{});
}
static std::string randomHex(size_t n) {
    std::vector<unsigned char> b(n);
    if(BCryptGenRandom(nullptr,b.data(),(ULONG)n,BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0) throw std::runtime_error("Secure random failed");
    return hex(b.data(),n);
}
static void logEvent(const std::string& event,const std::string& detail="") {
    if(dataDir.empty()) return;
    std::ofstream f(dataDir/L"audit.jsonl",std::ios::app);
    f<<json({{"event",event},{"detail",detail},{"pid",GetCurrentProcessId()},
        {"uptime_ms",GetTickCount64()}}).dump()<<"\n";
}
static json vector3(const vec3_t& v) {
    json a=json::array();
    for(int i=0;i<3;++i) {if(!std::isfinite(v[i])) throw std::runtime_error("Nonfinite SDK vector"); a.push_back(v[i]);}
    return a;
}
static json caps() {
    return {{"protocol",1},{"plugin","jack-codex-native-0.3"},{"api_level",10},
        {"architecture","x64"},{"editor_version",versionString},{"interface_bytes",sizeof(api)},
        {"read_document",true},{"read_selection",true},{"capture_trigger","automatic on-demand native dispatcher"},
        {"automatic_refresh",dispatchWindow!=nullptr},{"mutations",editEnabled&&!editFaulted},{"undo_redo",false},
        {"dispatcher","plugin-owned Win32 message-only window on editor thread"},
        {"edit_operations",json::array({"create_brush","duplicate_brush","move_brush","rotate_brush_z","create_entity","move_entity","set_entity_property"})},
        {"undo_transactions",true},{"plan_before_apply",true},{"faulted",editFaulted.load()},
        {"experimental",true},{"modified_notification_reliable",false},{"save_as_required",true},
        {"document_path_available",false},{"read_only",!editEnabled},{"isolated_copy_only",true},
        {"max_entities",8192},{"max_brushes",32768},{"detail_sample",64},{"max_selected_details",128}};
}
static json capture() {
    if(GetCurrentThreadId()!=editorThread) throw std::runtime_error("Editor-thread guard");
    qWorld_t* wp=api.pfnGlobal_GetCurrentWorld(); qWorld_t world{};
    if(!wp) return {{"has_document",false}};
    if(!readValue(wp,world)) throw std::runtime_error("World layout unreadable");
    json entities=json::array(),brushes=json::array();
    std::set<qEntity_t*> seenEntities; std::set<qBrush_t*> seenBrushes;
    for(qEntity_t* p=world.m_entityList;p;) {
        if(seenEntities.size()>=8192 || !seenEntities.insert(p).second) throw std::runtime_error("Entity limit/cycle");
        qEntity_t e{}; if(!readValue(p,e) || e.m_ownerWorld!=wp) throw std::runtime_error("Entity layout mismatch");
        const bool includeEntity=seenEntities.size()<=64 || (e.m_editorFlags&EFL_SELECTED);
        if(includeEntity && entities.size()>=192) throw std::runtime_error("Too many selected entity details; select fewer than 128 objects");
        json props=json::object(); std::set<epair_t*> pairs;
        if(includeEntity) {
        for(epair_t* pp=e.epairs;pp;) {
            if(pairs.size()>=128 || !pairs.insert(pp).second) throw std::runtime_error("Property limit/cycle");
            epair_t pair{};if(!readValue(pp,pair)) throw std::runtime_error("Property pointer invalid");
            props[text(pair.key)]=text(pair.value); pp=pair.next;
        }
        entities.push_back({{"editor_id",e.m_editorId},{"classname",text(e.m_className)},
            {"targetname",text(e.m_targetName)},{"origin",vector3(e.m_vecOrigin)},
            {"properties",props},{"selected",bool(e.m_editorFlags&EFL_SELECTED)}});
        }
        for(qBrush_t* bp=e.m_brushList;bp;) {
            if(seenBrushes.size()>=32768 || !seenBrushes.insert(bp).second) throw std::runtime_error("Brush limit/cycle");
            qBrush_t b{};if(!readValue(bp,b) || b.m_ownerEntity!=p) throw std::runtime_error("Brush layout mismatch");
            const bool includeBrush=seenBrushes.size()<=64 || (b.m_editorFlags&EFL_SELECTED);
            if(includeBrush && brushes.size()>=192) throw std::runtime_error("Too many selected brush details; select fewer than 128 objects");
            if(includeBrush) brushes.push_back({{"editor_id",b.m_editorId},{"owner_editor_id",e.m_editorId},
                {"min",vector3(b.m_bboxMin)},{"max",vector3(b.m_bboxMax)},
                {"selected",bool(b.m_editorFlags&EFL_SELECTED)}});
            bp=b.next;
        }
        p=e.next;
    }
    json selectedEntities=json::array(),selectedBrushes=json::array();
    std::set<qEntity_t*> se;std::set<qBrush_t*> sb;
    for(auto p=world.m_selEntityList;p;) {
        if(se.size()>=128 || !seenEntities.count(p)||!se.insert(p).second) throw std::runtime_error("Selection entity mismatch/limit");
        qEntity_t e{};if(!readValue(p,e)) throw std::runtime_error("Selection entity unreadable");
        selectedEntities.push_back(e.m_editorId);p=e.selectedNext;
    }
    for(auto p=world.m_selBrushList;p;) {
        if(sb.size()>=128 || !seenBrushes.count(p)||!sb.insert(p).second) throw std::runtime_error("Selection brush mismatch/limit");
        qBrush_t b{};if(!readValue(p,b)) throw std::runtime_error("Selection brush unreadable");
        selectedBrushes.push_back(b.m_editorId);p=b.selectedNext;
    }
    return {{"has_document",true},{"entities",entities},{"brushes",brushes},
        {"entity_count",seenEntities.size()},{"brush_count",seenBrushes.size()},
        {"details_truncated",entities.size()<seenEntities.size() || brushes.size()<seenBrushes.size()},
        {"detail_note","First 64 entities/brushes plus selected objects; export MAP for full analysis"},
        {"selection",{{"entities",selectedEntities},{"brushes",selectedBrushes},
            {"face_selection_present",world.m_selFaceList!=nullptr},
            {"other_selection_present",world.m_selCamera||world.m_selGroupList||world.m_selNodeList}}},
        {"path",nullptr},{"path_note","SDK exposes world data, not a verified document path"}};
}
static void refresh(int) {
    if(!ready) return;
    try {
        json doc=capture();
        json s={{"ok",true},{"generation",++generation},{"captured_tick_ms",GetTickCount64()},
            {"snapshot_fingerprint",digest(doc.dump())},{"document",doc}};
        if(s.dump().size()>MAX_MESSAGE-4096) throw std::runtime_error("Snapshot above IPC limit");
        {std::lock_guard<std::mutex> g(lockSnapshot);snapshot=std::move(s);}
        logEvent("snapshot",std::to_string(generation));
        api.pfnSys_Printf("Codex read-only snapshot %llu captured. No map changes.",generation);
    } catch(const std::exception& e) {
        {std::lock_guard<std::mutex> g(lockSnapshot);snapshot={{"ok",false},{"error",e.what()}};}
        logEvent("snapshot_rejected",e.what());
        api.pfnSys_Printf("Codex read-only probe rejected snapshot: %s",e.what());
    }
}
#include "native_edits.h"
static bool transfer(HANDLE pipe,void* bytes,DWORD n,bool write,DWORD& done) {
    OVERLAPPED ov{}; ov.hEvent=CreateEventW(nullptr,TRUE,FALSE,nullptr); if(!ov.hEvent) return false;
    BOOL ok=write?WriteFile(pipe,bytes,n,&done,&ov):ReadFile(pipe,bytes,n,&done,&ov);
    if(!ok && GetLastError()==ERROR_IO_PENDING) {
        if(WaitForSingleObject(ov.hEvent,3000)==WAIT_OBJECT_0) ok=GetOverlappedResult(pipe,&ov,&done,FALSE);
        else {CancelIoEx(pipe,&ov); GetOverlappedResult(pipe,&ov,&done,TRUE);ok=FALSE;}
    }
    CloseHandle(ov.hEvent);return ok && done>0;
}
static DWORD WINAPI serve(void*) {
    SECURITY_ATTRIBUTES sa{sizeof(sa),descriptor,FALSE};
    HANDLE p=CreateNamedPipeW(pipeName.c_str(),PIPE_ACCESS_DUPLEX|FILE_FLAG_OVERLAPPED|FILE_FLAG_FIRST_PIPE_INSTANCE,
        PIPE_TYPE_MESSAGE|PIPE_READMODE_MESSAGE|PIPE_WAIT|PIPE_REJECT_REMOTE_CLIENTS,1,MAX_MESSAGE,8192,3000,&sa);
    if(p==INVALID_HANDLE_VALUE) {logEvent("pipe_failed",std::to_string(GetLastError()));return 1;}
    // Publish after owning the named pipe, never before.
    const std::string pipeAscii="\\\\.\\pipe\\JACKCodex-"+std::to_string(GetCurrentProcessId())+"-"+sessionId;
    json endpoint={{"protocol",1},{"pid",GetCurrentProcessId()},{"session_id",sessionId},
        {"pipe",pipeAscii},{"token",token},{"exe_sha256",EXE_SHA}};
    std::ofstream(dataDir/L"endpoint.json",std::ios::trunc)<<endpoint.dump(2);
    logEvent("pipe_ready");
    for(;;) {
        OVERLAPPED ov{};ov.hEvent=CreateEventW(nullptr,TRUE,FALSE,nullptr);
        BOOL connected=ConnectNamedPipe(p,&ov); DWORD err=GetLastError();
        if(!connected && err==ERROR_IO_PENDING) {WaitForSingleObject(ov.hEvent,INFINITE);DWORD n;connected=GetOverlappedResult(p,&ov,&n,FALSE);}
        else if(!connected && err==ERROR_PIPE_CONNECTED) connected=TRUE;
        CloseHandle(ov.hEvent);
        if(!connected) {DisconnectNamedPipe(p);continue;}
        char buffer[8193]{};DWORD got=0;
        if(transfer(p,buffer,8192,false,got)) {
            try {
                json q=json::parse(buffer,buffer+got);
                std::string id=q.value("id",std::string{}),method=q.value("method",std::string{});
                if(q.value("token",std::string{})!=token) throw std::runtime_error("Unauthorized");
                if(id.empty()||id.size()>80) throw std::runtime_error("Invalid request ID");
                json result;
                if(method=="capabilities") result=caps();
                else if(method=="snapshot" || method=="plan_edits" || method=="apply_edits") {
                    result=dispatchRequest(q);
                } else throw std::runtime_error("Unsupported native method");
                std::string reply=json({{"id",id},{"session_id",sessionId},{"result",result}}).dump();
                DWORD done=0;transfer(p,reply.data(),(DWORD)reply.size(),true,done);
            } catch(const std::exception&) {
                // Never log tokens or raw request data.
                logEvent("request_rejected");std::string s="{\"error\":\"request_rejected\"}";DWORD done=0;transfer(p,s.data(),(DWORD)s.size(),true,done);
            }
            // A bounded client ACK prevents DisconnectNamedPipe discarding a
            // buffered response, without an unbounded FlushFileBuffers wait.
            char ack[4]{};DWORD ackBytes=0;transfer(p,ack,3,false,ackBytes);
        }
        DisconnectNamedPipe(p);
    }
}
static bool setup() {
    wchar_t path[32768]{};if(!GetModuleFileNameW(nullptr,path,32768)) return false;
    fs::path exe(path);dataDir=exe.parent_path()/L"codex-bridge";
    // This development plugin cannot activate in the real editor installation.
    if(!fs::exists(exe.parent_path()/L"CODEX_DISPOSABLE_EDITOR_ONLY.marker")) return false;
    if(digest(fileBytes(exe))!=EXE_SHA) return false;
    HANDLE tok=nullptr; if(!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&tok)) return false;
    DWORD size=0;GetTokenInformation(tok,TokenUser,nullptr,0,&size);std::vector<char> buf(size);
    if(!GetTokenInformation(tok,TokenUser,buf.data(),size,&size)) {CloseHandle(tok);return false;}
    CloseHandle(tok);LPWSTR sid=nullptr;
    if(!ConvertSidToStringSidW(((TOKEN_USER*)buf.data())->User.Sid,&sid)) return false;
    std::wstring acl=L"D:P(A;OICI;FA;;;"+std::wstring(sid)+L")";LocalFree(sid);
    if(!ConvertStringSecurityDescriptorToSecurityDescriptorW(acl.c_str(),SDDL_REVISION_1,&descriptor,nullptr)) return false;
    SECURITY_ATTRIBUTES sa{sizeof(sa),descriptor,FALSE};
    // Refuse pre-existing data directories: don't trust inherited/permissive ACLs.
    if(!CreateDirectoryW(dataDir.c_str(),&sa)) return false;
    token=randomHex(32);sessionId=randomHex(16);
    pipeName=L"\\\\.\\pipe\\JACKCodex-"+std::to_wstring(GetCurrentProcessId())+L"-"+std::wstring(sessionId.begin(),sessionId.end());
    snapshot={{"ok",false},{"error","No capture yet. Use Plugins > Codex > Capture read-only snapshot."}};
    // Pin our own DLL so no worker can execute unloaded code; process exit reclaims it.
    HMODULE module=nullptr;
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCWSTR)&setup,&module)) return false;
    if(!setupDispatcher(module)) return false;
    HANDLE worker=CreateThread(nullptr,0,serve,nullptr,0,nullptr);if(!worker) return false;CloseHandle(worker);
    return true;
}
DLL_EXPORT int vpMain(plugin_funcs_t* host,int level) {
    try {
        if(level!=10) return 10;
        size_t bytes=0;if(!readValue((size_t*)host,bytes)||bytes!=sizeof(api)) return -1;
        if(!readValue(host,api)||!api.pfnV_VersionString||!api.pfnGlobal_GetCurrentWorld||!api.pfnSys_Printf) return -1;
        versionString=text(api.pfnV_VersionString());
        if(versionString.find("1.1.3773")==std::string::npos) return -1;
        editorThread=GetCurrentThreadId();ready=setup();
        if(!ready) return -1;logEvent("plugin_loaded",versionString);return 0;
    } catch(...) {return -1;}
}
static pluginActionDesc_t action={"Capture read-only snapshot","Capture current map and selection; never modifies the map","Codex",0,0,1,refresh};
DLL_EXPORT int vpEnumActions(pfnRegisterAction registration,void* manager) {
    if(!ready||!registration) return 0;registration(&action,manager);return 1;
}
