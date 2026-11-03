"""Generate valid convex GoldSrc MAP geometry; no third-party map/assets."""
def box(lo,hi,texture):
    x,y,z=lo;X,Y,Z=hi
    planes=[((x,y,z),(x,Y,z),(X,Y,z)),((x,y,Z),(X,y,Z),(X,Y,Z)),((x,y,z),(X,y,z),(X,y,Z)),
            ((x,Y,z),(x,Y,Z),(X,Y,Z)),((x,y,z),(x,y,Z),(x,Y,Z)),((X,y,z),(X,Y,z),(X,Y,Z))]
    lines=[]
    for a,b,c in planes:
        u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        axis=max(range(3),key=lambda i:abs(n[i]))
        uv='[ 0 1 0 0 ] [ 0 0 -1 0 ]' if axis==0 else '[ 1 0 0 0 ] [ 0 0 -1 0 ]' if axis==1 else '[ 1 0 0 0 ] [ 0 -1 0 0 ]'
        lines.append(' '.join('( %s %s %s )'%p for p in (a,c,b))+f' {texture} {uv} 0 1 1')
    return '{\n'+'\n'.join(lines)+'\n}\n'
def room_text(texture='AAATRIGGER',wad=''):
    if any(c in texture+wad for c in ('"','\n','\r')):raise ValueError('Invalid texture/WAD text')
    walls=[((-256,-256,-32),(256,256,0)),((-256,-256,256),(256,256,288)),
           ((-288,-288,-32),(-256,288,288)),((256,-288,-32),(288,288,288)),
           ((-256,-288,-32),(256,-256,288)),((-256,256,-32),(256,288,288)),
           ((-128,-32,0),(-64,32,64)),((64,-32,0),(128,32,64))]
    return '{\n"classname" "worldspawn"\n"mapversion" "220"\n"wad" "'+wad+'"\n'+''.join(box(*b,texture) for b in walls)+'}\n{\n"classname" "info_player_start"\n"targetname" "codex_probe_spawn"\n"origin" "0 128 40"\n}\n'
