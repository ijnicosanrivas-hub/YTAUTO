"""Extrae los nueve personajes de un render (p. ej. el de las figuras LEGO de Batman) como PNG con transparencia.

Uso:  python scripts/extraer_figuras.py render.jpg --modelo isnet-general-use.onnx [--salida assets/personajes]
Requiere (solo para este paso): numpy, pillow, onnxruntime y el modelo ISNet «general use» en formato ONNX.
Las cajas están medidas para el render de 1344×756 de las nueve figuras sobre la plataforma; con otro render hay que ajustarlas.
La salida (assets/personajes/) NO se versiona: son recortes de material de terceros. La sala los usa si existen y, si no,
dibuja las figuras de ladrillos.
"""
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BOX={'chief':(40,295,250,585),'publisher':(160,225,375,565),'scriptwriter':(315,320,495,580),'director':(455,325,625,555),
 'resources':(585,295,745,590),'reviewer':(730,315,875,560),'sound':(860,335,1010,590),'voice':(950,255,1170,570),'editor':(1110,310,1295,585)}

sess = None


def matte(img):
    w,h=img.size
    x=np.asarray(img.convert('RGB').resize((1024,1024), Image.BILINEAR),dtype=np.float32)/255.0
    x=(x-0.5)[None].transpose(0,3,1,2).astype(np.float32)
    out=sess.run(None,{'input_image':x})[0][0,0]
    out=(out-out.min())/(out.max()-out.min()+1e-8)
    return Image.fromarray((out*255).astype(np.uint8)).resize((w,h), Image.BILINEAR)

# zona donde puede estar el personaje + sus objetos (coordenadas del render original)
KEEP={'chief':(48,300,246,560),'publisher':(165,232,372,530),'scriptwriter':(330,322,490,562),'director':(458,328,618,536),
 'resources':(588,300,742,559),'reviewer':(738,320,870,534),'sound':(862,340,1008,564),'voice':(955,260,1165,560),'editor':(1118,314,1290,562)}
def label(mask):
    h,w=mask.shape; lab=np.zeros((h,w),np.int32); n=0; sizes=[0]
    for y in range(h):
        for x in range(w):
            if mask[y,x] and not lab[y,x]:
                n+=1; q=deque([(y,x)]); lab[y,x]=n; c=0
                while q:
                    cy,cx=q.popleft(); c+=1
                    for dy in(-1,0,1):
                        for dx in(-1,0,1):
                            ny,nx=cy+dy,cx+dx
                            if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not lab[ny,nx]: lab[ny,nx]=n; q.append((ny,nx))
                sizes.append(c)
    return lab,sizes
EXCL={'publisher':[(0,285,217,600)],'scriptwriter':[(0,0,358,600)],'voice':[(0,0,968,600)]}
def z(pts,ox,oy,k): return [(ox+x/k,oy+y/k) for x,y in pts]
POLY={'sound':z([(130,310),(350,300),(395,340),(405,470),(425,500),(420,530),(375,545),(345,560),(345,645),(130,645),(130,560),(160,520),(165,470),(120,420)],860,330,3),
 'voice':z([(590,320),(755,320),(790,420),(820,510),(825,545),(740,550),(730,440),(690,400),(650,440),(600,520),(560,545),(520,540),(545,470),(570,400)],950,250,2)}
def process(name, img):
    x0,y0,x1,y1=BOX[name]; crop=img.crop(BOX[name]); m=np.asarray(matte(crop),dtype=np.float32)/255.0
    a=np.clip((m-0.25)/0.55,0,1)
    H,W=a.shape
    # fuera de la zona del personaje y por debajo de la placa de nombre
    kx0,ky0,kx1,ky1=KEEP[name]; keep=np.zeros_like(a,bool); keep[max(0,ky0-y0):min(H,ky1-y0), max(0,kx0-x0):min(W,kx1-x0)]=True
    a[~keep]=0
    for (ex0,ey0,ex1,ey1) in EXCL.get(name,[]):
        a[max(0,ey0-y0):max(0,ey1-y0), max(0,ex0-x0):max(0,ex1-x0)]=0
    if name in POLY:
        pm=Image.new('L',(W,H),0); ImageDraw.Draw(pm).polygon([(px-x0,py-y0) for px,py in POLY[name]],fill=255)
        pm=np.asarray(pm.filter(ImageFilter.GaussianBlur(1.2)),dtype=np.float32)/255.0
        a=np.maximum(a,pm)
    if name=='voice':
        r=int(H*0.62); lo,hi=int(W*0.19),int(W*0.80); a[r:,:lo]=0; a[r:,hi:]=0; a[r:,lo:hi]=np.clip(a[r:,lo:hi]*6,0,1)
    mask=a>0.5; lab,sizes=label(mask)
    big=max(range(1,len(sizes)),key=lambda i:sizes[i]); keepl={big}
    for i in range(1,len(sizes)):
        if i!=big and sizes[i]>=180: keepl.add(i)   # objetos que se despegan (bastón, látigo, mazo…)
    sel=np.isin(lab,list(keepl))
    selimg=Image.fromarray((sel*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    a=a*(np.asarray(selimg)>0)
    rgba=np.dstack([np.asarray(crop,dtype=np.uint8),(a*255).astype(np.uint8)])
    ys,xs=np.where(a>0.04); bx0,bx1,by0,by1=xs.min(),xs.max()+1,ys.min(),ys.max()+1
    # centro de la base = centro de las últimas filas opacas
    last=a[max(by0,by1-14):by1]; cols=np.where((last>0.5).any(axis=0))[0]
    anchor=(cols.min()+cols.max())/2.0 if len(cols) else (bx0+bx1)/2
    out=Image.fromarray(rgba[by0:by1,bx0:bx1],'RGBA')
    return out, dict(anchor_x=float((anchor-bx0)/(bx1-bx0)), w=int(bx1-bx0), h=int(by1-by0), bbox=[int(x0+bx0),int(y0+by0),int(x0+bx1),int(y0+by1)])


def main() -> None:
    global sess
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("render")
    ap.add_argument("--modelo", required=True, help="isnet-general-use.onnx")
    ap.add_argument("--salida", default=str(Path(__file__).resolve().parents[1] / "assets" / "personajes"))
    a = ap.parse_args()
    import onnxruntime as ort
    sess = ort.InferenceSession(a.modelo, providers=["CPUExecutionProvider"])
    out = Path(a.salida); out.mkdir(parents=True, exist_ok=True)
    img = Image.open(a.render).convert("RGB"); meta = {}
    for n in BOX:
        s, mt = process(n, img); s.save(out / f"{n}.png"); meta[n] = mt; print(n, mt["w"], "x", mt["h"])
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
