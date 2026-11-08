"""Local RGSS1 map codec and deterministic previews using existing project assets."""
from __future__ import annotations
import json
from pathlib import Path
import sys
from plugin_tools import Ruby, ROOT, DEFAULT_GAME

local_pillow = ROOT / '.cache/map-render-lib'
if local_pillow.is_dir():
    sys.path.insert(0, str(local_pillow))
from PIL import Image, ImageDraw

QUADRANTS = json.loads((ROOT / 'scripts/fixtures/xp-autotile-quadrants.json').read_text())


class MapCodec:
    def __init__(self, game=DEFAULT_GAME):
        self.game = game
        self.ruby = Ruby(game)
        self.ruby.load_source((ROOT / 'scripts/fixtures/rgss-map-data.rb').read_text(encoding='utf-8'), 'RGSS1 map data')
        self.ruby.load_source('module NordelunaOnline;class Error<StandardError;end;MAX_RESPONSE=16777216;end', 'codec scope')
        self.ruby.load_source((game / 'Plugins/Nordeluna Online/002_JSON.rb').read_text(encoding='utf-8'), 'JSON codec')
        self.ruby.load_source('''
def export_map_value(value)
  case value
  when NilClass, TrueClass, FalseClass, Integer then value
  when Symbol then value.to_s
  when Float then value.to_s
  when String
    text=value.dup.force_encoding('UTF-8')
    text.valid_encoding? ? text : value.dup.force_encoding('Windows-1252').encode('UTF-8', invalid: :replace, undef: :replace)
  when Array then value.map { |v| export_map_value(v) }
  when Hash then value.to_h { |k,v| [k.to_s,export_map_value(v)] }
  when Table then {'dimensions'=>[value.dimensions,value.xsize,value.ysize,value.zsize,value.values.length], 'values'=>value.values}
  when Color, Tone then {'native_type'=>value.class.name}
  else value.instance_variables.to_h { |k| [k.to_s.delete_prefix('@'),export_map_value(value.instance_variable_get(k))] }
  end
end
''', 'map export')

    def read(self, name, variable):
        packet=(self.game / name).read_bytes().hex()
        self.ruby.evaluate(f'${variable}=Marshal.load([{json.dumps(packet)}].pack("H*"));"loaded"')
        return json.loads(self.ruby.evaluate(f'NordelunaOnline::JSON.dump(export_map_value(${variable}))'))

    def plan(self, plan, variable):
        packet=json.dumps(plan, ensure_ascii=False).encode('utf-8').hex()
        self.ruby.evaluate(f'${variable}=social_map_from_plan(NordelunaOnline::JSON.parse([{json.dumps(packet)}].pack("H*").force_encoding("UTF-8")));"built"')

    def dump(self, expression, path):
        data=bytes.fromhex(self.ruby.evaluate(f'Marshal.dump({expression}).unpack1("H*")'))
        # A second load validates Table headers and every serialized object.
        result=self.ruby.evaluate(f'Marshal.dump(Marshal.load([{json.dumps(data.hex())}].pack("H*"))).unpack1("H*")')
        if bytes.fromhex(result)!=data:raise RuntimeError('RGSS serialization did not round-trip')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)


def graphic_path(game, folder, name):
    if not name:return None
    base=game/'Graphics'/folder
    matches=[p for p in base.iterdir() if p.stem.casefold()==name.casefold()]
    return matches[0] if matches else None


class MapRenderer:
    def __init__(self, tilesets, game=DEFAULT_GAME):
        self.game,self.tilesets=game,tilesets
        self.cache={}
        self.images={}

    def tile(self, tileset_id, tile_id):
        key=(tileset_id,tile_id)
        if key in self.cache:return self.cache[key]
        meta=self.tilesets[tileset_id]
        if tileset_id not in self.images:
            main=Image.open(graphic_path(self.game,'Tilesets',meta['tileset_name'])).convert('RGBA')
            autos=[Image.open(path).convert('RGBA') if (path:=graphic_path(self.game,'Autotiles',name)) else None for name in meta['autotile_names']]
            self.images[tileset_id]=(main,autos)
        main,autos=self.images[tileset_id]
        tile=Image.new('RGBA',(32,32))
        if tile_id>=384:
            x,y=(tile_id-384)%8*32,(tile_id-384)//8*32
            if y+32>main.height:raise ValueError(f'Out-of-sheet tile {tile_id}')
            tile=main.crop((x,y,x+32,y+32))
        elif tile_id>=48:
            image=autos[tile_id//48-1]
            if image is None:raise ValueError(f'Missing autotile for tile {tile_id}')
            if image.height==32:tile=image.crop((0,0,32,32))
            else:
                for i,(x,y) in enumerate(QUADRANTS[tile_id%48]):
                    tile.alpha_composite(image.crop((x,y,x+16,y+16)),((i%2)*16,(i//2)*16))
        self.cache[key]=tile
        return tile

    def render(self, plan, markers=False):
        w,h=plan['width'],plan['height'];values=plan['values'];tid=plan['tileset_id']
        image=Image.new('RGBA',(w*32,h*32),(18,21,28,255))
        # Roofs/treetops keep their native priorities. The second pass below
        # puts the stationary character preview below those foreground pieces.
        for z in range(3):
            for y in range(h):
                for x in range(w):
                    tile=values[(z*h+y)*w+x]
                    if tile:image.alpha_composite(self.tile(tid,tile),(x*32,y*32))
        for event in plan['events']:
            name=event.get('character','')
            path=graphic_path(self.game,'Characters',name)
            if path:
                sheet=Image.open(path).convert('RGBA');sw,sh=sheet.width//4,sheet.height//4
                direction=event.get('direction',2);sy=(direction//2-1)*sh
                frame=sheet.crop((0,sy,sw,sy+sh))
                image.alpha_composite(frame,(event['x']*32+16-sw//2,event['y']*32+32-sh))
        priorities=self.tilesets[tid]['priorities']['values']
        for z in range(3):
            for y in range(h):
                for x in range(w):
                    tile=values[(z*h+y)*w+x]
                    if tile and priorities[tile]>0:image.alpha_composite(self.tile(tid,tile),(x*32,y*32))
        if markers:
            draw=ImageDraw.Draw(image)
            for event in plan['events']:
                if event.get('hidden'):continue
                x,y=event['x']*32,event['y']*32
                draw.rectangle((x,y,x+31,y+31),outline='#ffba5a')
                draw.text((x+2,y+1),str(event['id']),fill='white',stroke_width=1,stroke_fill='black')
        return image.convert('RGB')
