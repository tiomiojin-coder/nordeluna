"""Check the generated map pack using Essentials' actual movement methods."""
from collections import deque
import json
from pathlib import Path
import sys
from rgss_map_tools import MapCodec,ROOT,DEFAULT_GAME,graphic_path

OUT=ROOT/'build/social-maps'
MOVES=[(0,1,2,1,8),(0,-1,8,8,1),(-1,0,4,2,4),(1,0,6,4,2)]
ENTRIES={39:(34,59),40:(19,31),41:(18,25)}


def main():
    codec=MapCodec();sets=codec.read('Data/Tilesets.rxdata','tilesets')
    codec.ruby.load_source((DEFAULT_GAME/'_extracted_scripts/042_Game_Map.rb').read_text(encoding='utf-8'),'actual Essentials Game_Map')
    codec.ruby.load_source('''
module GameData
  module TerrainTag
    class NoneTag
      def id; :None; end
      def method_missing(*args); false; end
    end
    NONE=NoneTag.new
    def self.try_get(id); raise 'Unexpected nonzero terrain' unless id==0; NONE;end
  end
end
$PokemonGlobal=Struct.new(:bridge,:surfing,:bicycle).new(0,false,false)
$game_player=Struct.new(:x,:y).new(0,0)
''','neutral terrain (all generated tiles verified as tag zero)')
    all_plans={mid:json.loads((OUT/f'map-{mid}-plan.json').read_text(encoding='utf-8')) for mid in [39,40,41]}
    results=[];errors=[];native_masks={}
    for mid,plan in all_plans.items():
        w,h=plan['width'],plan['height'];meta=sets[plan['tileset_id']]
        assert plan['tileset_id']==(34 if mid==39 else 24)
        assert len(plan['values'])==w*h*3
        assert {meta['terrain_tags']['values'][t] for t in plan['values'] if t}=={0}
        codec.plan(plan,'verify_map')
        codec.ruby.evaluate(f'''$test_map=Game_Map.new
$test_map.instance_variable_set(:@map,$verify_map)
$test_map.instance_variable_set(:@events,{{}})
$test_map.instance_variable_set(:@map_id,{mid})
$test_map.instance_variable_set(:@passages,$tilesets[{plan['tileset_id']}].passages)
$test_map.instance_variable_set(:@priorities,$tilesets[{plan['tileset_id']}].priorities)
$test_map.instance_variable_set(:@terrain_tags,$tilesets[{plan['tileset_id']}].terrain_tags)
"ready"''')
        # Run native source for every cell and direction, rather than reimplement
        # passage/priority semantics in the authoring tool.
        masks=json.loads(codec.ruby.evaluate('''NordelunaOnline::JSON.dump((0...$verify_map.height).flat_map do |y|
 (0...$verify_map.width).map do |x|
  $game_player.x=x;$game_player.y=y
  [2,4,6,8].inject(0) { |bits,d| bits | ($test_map.passable?(x,y,d,$game_player) ? (1<<(d/2-1)) : 0) }
 end
end)'''))
        native_masks[mid]=masks
        occupied={(e['x'],e['y']) for e in plan['events'] if e.get('character') and not e.get('through')}
        seen={ENTRIES[mid]};queue=deque(seen)
        if not masks[ENTRIES[mid][1]*w+ENTRIES[mid][0]]:errors.append(f'Map {mid}: blocked spawn')
        while queue:
            x,y=queue.popleft()
            for dx,dy,d,bit,reverse in MOVES:
                nx,ny=x+dx,y+dy
                if not (0<=nx<w and 0<=ny<h) or (nx,ny) in occupied or (nx,ny) in seen:continue
                if masks[y*w+x]&bit and masks[ny*w+nx]&reverse:
                    seen.add((nx,ny));queue.append((nx,ny))
        for event in plan['events']:
            x,y=event['x'],event['y']
            assert 0<=x<w and 0<=y<h
            if event.get('character') and not graphic_path(DEFAULT_GAME,'Characters',event['character']):
                errors.append(f'Map {mid} event {event["id"]}: missing character')
            if event.get('hidden'):continue
            accessible=(x,y) in seen and not event.get('character')
            for dx,dy,*_ in MOVES:
                accessible|=(x+dx,y+dy) in seen
                cx,cy=x+dx,y+dy
                if 0<=cx<w and 0<=cy<h:
                    counter=any(meta['passages']['values'][plan['values'][(z*h+cy)*w+cx]]&128 for z in range(3))
                    accessible|=counter and (x+2*dx,y+2*dy) in seen
            if not accessible:errors.append(f'Map {mid} event {event["id"]} ({event["name"]}) unreachable')
            if event['trigger']==1 and (x,y) not in seen:
                errors.append(f'Map {mid}: blocked exit event {event["id"]} at {x},{y}')
            for code,indent,args in event['commands']:
                assert indent==0 and code in [0,101,355]
                if code==355:
                    codec.ruby.evaluate('RubyVM::InstructionSequence.compile(['+json.dumps(args[0].encode('utf-8').hex())+'].pack("H*").force_encoding("UTF-8"));"valid"')
        if mid==39 and (21,19) not in seen:errors.append('Old plaza arrival 21,19 is no longer reachable')
        results.append(dict(id=mid,reachable_cells=len(seen),events=len(plan['events'])))
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for row in manifest['maps']:
        for warp in row['transfers']:
            mid,x,y,direction=warp['target'];target=all_plans[mid]
            assert 0<=x<target['width'] and 0<=y<target['height'] and direction in [2,4,6,8]
            if not native_masks[mid][y*target['width']+x]:errors.append(f'Blocked warp destination {warp["target"]}')
            if any(e['trigger']==1 and (e['x'],e['y'])==(x,y) for e in target['events']):errors.append('Immediate return loop at arrival')
    report=dict(native_engine='Game_Map.passable? + playerPassable?',maps=results,errors=errors)
    (OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
