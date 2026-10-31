"""Generate clearly labeled synthetic tray images. They test the software, not any model."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

ROOT=Path(__file__).resolve().parent.parent
DEST=ROOT/'datasets'/'samples'
DEST.mkdir(exist_ok=True,parents=True)

def tray(variant:str):
    im=Image.new('RGB',(480,320),'#e8ecf2')
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((70,40,410,280),15,fill='#cfd8de',outline='#657687',width=6)
    d.rounded_rectangle((95,85,155,150),6,fill='#2d8dcb')
    d.rounded_rectangle((95,180,155,250),6,fill='#75b7dc')
    d.ellipse((320,100,370,150),fill='#f3ce64',outline='#9e751a',width=4)
    box=(220,125,305,215) if variant=='alternate_view' else (200,125,285,215)
    if variant not in ('absent','occluded'):
        d.polygon([(box[0],box[1]),(box[2],box[1]),(box[2],box[3]-17),
                   ((box[0]+box[2])//2,box[3]),(box[0],box[3]-17)],fill='#c33f3c')
        d.rectangle((box[0]+17,box[1]+22,box[2]-17,box[1]+31),fill='#f6c9bd')
    if variant=='occluded':
        d.rounded_rectangle((180,95,312,238),8,fill='#485667',outline='#1e293b',width=3)
        d.text((195,155),'BLOCKED',fill='#ffffff')
    if variant=='low_light':
        im=ImageEnhance.Brightness(im).enhance(0.28)
    d=ImageDraw.Draw(im)
    d.text((18,12),f'SYNTHETIC FIXTURE: {variant}',fill='#6b7280' if variant!='low_light' else '#a9a9a9')
    im.save(DEST/f'{variant}.png')

if __name__=='__main__':
    for name in ['normal','low_light','occluded','alternate_view','absent']:tray(name)
    print('Generated 5 synthetic fixture images in datasets/samples/')
