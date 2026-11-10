"""Validate the author's compiled species tables in an isolated Ruby process."""
import argparse
import json
from pathlib import Path
import sys

from plugin_tools import DEFAULT_GAME, Ruby


def validate(game):
    sources = {
        'species.dat': ('pokemon.txt', 'pokemon_forms.txt'),
        'species_metrics.dat': ('pokemon_metrics.txt',),
        'moves.dat': ('moves.txt',),
        'abilities.dat': ('abilities.txt',),
        'items.dat': ('items.txt',),
        'types.dat': ('types.txt',),
        'regional_dexes.dat': ('regional_dexes.txt',),
    }
    for compiled, names in sources.items():
        target = game / 'Data' / compiled
        if not target.is_file():
            raise ValueError('Arquivo compilado ausente: ' + compiled)
        for name in names:
            source = game / 'PBS' / name
            if source.is_file() and source.stat().st_mtime > target.stat().st_mtime + 2:
                raise ValueError('Compile o jogo no RPG Maker XP antes de publicar: ' + name)
    ruby = Ruby(game)
    ruby.evaluate('module GameData; class Species;end;class SpeciesMetrics;end;'
                  'class Move;end;class Ability;end;class Item;end;class Type;end;end;'
                  '$tables={};"ready"')
    for name in ['species', 'species_metrics', 'moves', 'abilities', 'items', 'types']:
        body = (game / 'Data' / (name + '.dat')).read_bytes()
        ruby.evaluate('$tables[%s]=Marshal.load([%s].pack("H*"));"loaded"' %
                      (json.dumps(name), json.dumps(body.hex())))
    dexes=(game/'Data/regional_dexes.dat').read_bytes()
    ruby.evaluate('$tables["dexes"]=Marshal.load([%s].pack("H*"));"loaded"' % json.dumps(dexes.hex()))
    return ruby.evaluate('''
species=$tables.fetch('species')
raise 'Tabela de especies vazia ou invalida' unless species.is_a?(Hash) && !species.empty?
reference=proc do |table,id,owner|
  raise "#{owner}: referencia desconhecida #{table}/#{id}" unless $tables.fetch(table).key?(id)
end
species.each do |id,entry|
  raise "Especie invalida: #{id}" unless entry.is_a?(GameData::Species) && entry.instance_variable_get(:@id)==id
  base=entry.instance_variable_get(:@species)
  reference.call('species',base,id)
  {:@types=>'types',:@abilities=>'abilities',:@hidden_abilities=>'abilities',
   :@tutor_moves=>'moves',:@egg_moves=>'moves',:@offspring=>'species',
   :@wild_item_common=>'items',:@wild_item_uncommon=>'items',:@wild_item_rare=>'items'}.each do |field,table|
    Array(entry.instance_variable_get(field)).each { |value| reference.call(table,value,id) }
  end
  Array(entry.instance_variable_get(:@moves)).each { |row| reference.call('moves',row[1],id) }
  Array(entry.instance_variable_get(:@evolutions)).each { |row| reference.call('species',row[0],id) }
  {:@mega_stone=>'items',:@mega_move=>'moves',:@incense=>'items'}.each do |field,table|
    value=entry.instance_variable_get(field)
    reference.call(table,value,id) if value
  end
end
metrics=$tables.fetch('species_metrics')
raise 'Metricas invalidas' unless metrics.is_a?(Hash)
metrics.each do |id,entry|
  raise "Metrica invalida: #{id}" unless entry.is_a?(GameData::SpeciesMetrics)
  reference.call('species',entry.instance_variable_get(:@species),id)
end
types=$tables.fetch('types')
types.each do |id,entry|
  [:@weaknesses,:@resistances,:@immunities].each do |field|
    Array(entry.instance_variable_get(field)).each { |value| reference.call('types',value,id) }
  end
end
$tables.fetch('moves').each do |id,entry|
  reference.call('types',entry.instance_variable_get(:@type),id)
end
$tables.fetch('items').each do |id,entry|
  move=entry.instance_variable_get(:@move)
  reference.call('moves',move,id) if move
end
dexes=$tables.fetch('dexes')
raise 'Pokedex regional invalida' unless dexes.is_a?(Array)
dexes.compact.each do |dex|
  raise 'Lista da Pokedex invalida' unless dex.is_a?(Array)
  dex.compact.each { |id| reference.call('species',id,'Pokedex') }
end
"PASS: #{species.length} especies/formas; #{metrics.length} metricas; referencias validas."
''')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, default=DEFAULT_GAME)
    args = parser.parse_args()
    try:
        print(validate(args.game))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
