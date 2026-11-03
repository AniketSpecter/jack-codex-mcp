// Tests the real capture implementation with SDK-layout objects, no live editor.
#include "bridge.cpp"
#include <iostream>
static qWorld_t testWorld{};
static qWorld_t* testCurrentWorld(){return &testWorld;}
int main(){
    editorThread=GetCurrentThreadId();api.pfnGlobal_GetCurrentWorld=testCurrentWorld;
    std::vector<qEntity_t> es(600);
    std::vector<qBrush_t> bs(1600);
    for(size_t i=0;i<es.size();++i){
        auto& e=es[i];e.m_ownerWorld=&testWorld;e.m_editorId=(int)i+1;
        e.next=i+1<es.size()?&es[i+1]:nullptr;e.m_className=(char*)(i?"info_target":"worldspawn");
    }
    testWorld.m_entityList=es.data();
    es[0].m_brushList=bs.data();
    for(size_t i=0;i<bs.size();++i){
        auto& b=bs[i];b.m_ownerEntity=&es[0];b.m_editorId=(int)i+1;
        b.next=i+1<bs.size()?&bs[i+1]:nullptr;
        b.m_bboxMin[0]=(float)i;b.m_bboxMax[0]=(float)i+16;
    }
    es.back().m_editorFlags=EFL_SELECTED;testWorld.m_selEntityList=&es.back();
    bs.back().m_editorFlags=EFL_SELECTED;testWorld.m_selBrushList=&bs.back();
    json result=capture();
    if(result["entity_count"]!=600||result["brush_count"]!=1600||!result["details_truncated"]||
       result["entities"].size()!=65||result["brushes"].size()!=65||
       result["selection"]["entities"][0]!=600||result["selection"]["brushes"][0]!=1600||
       result["brushes"].back()["min"][0]!=1599) return 1;
    bs.back().next=bs.data();bool rejected=false;
    try{capture();}catch(const std::runtime_error&){rejected=true;}
    if(!rejected)return 2;
    bs.back().next=nullptr;bs[1].m_ownerEntity=nullptr;rejected=false;
    try{capture();}catch(const std::runtime_error&){rejected=true;}
    if(!rejected)return 3;
    std::cout<<"PASS: 600 entities / 1600 brushes; selected objects beyond sample; cycle and owner mismatch rejected\n";
    return 0;
}
