"""Ruby configuration interchange for the local content editor (never remote code)."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server.content import validate_content


def ruby_literal(value, depth=0):
    if value is None:return 'nil'
    if type(value) is bool:return 'true' if value else 'false'
    if type(value) is int:return str(value)
    if isinstance(value,str):return "'"+value.replace('\\','\\\\').replace("'","\\'")+"'"
    if isinstance(value,list):return '['+', '.join(ruby_literal(v,depth+1) for v in value)+']'
    if isinstance(value,dict):
        pad='  '*(depth+1)
        return '{\n'+',\n'.join(pad+ruby_literal(k)+' => '+ruby_literal(v,depth+1) for k,v in value.items())+'\n'+'  '*depth+'}'
    raise ValueError('Tipo nao suportado no arquivo Ruby.')


def export_ruby(content):
    return ("# Conteudo online Nordeluna. Este arquivo fica no seu PC; publique pelo painel.\n"
            "# IDs existentes preservam os resgates; use ID novo para uma missao nova.\n"
            "# Atividades disponiveis: visit, battle, trade. Valores em Luna Coins.\n"
            "# Nao coloque senhas ou tokens neste arquivo.\n"
            "NORDELUNA_CONTENT = "+ruby_literal(validate_content(content))+"\n")


def read_ruby(source):
    # Evaluate only an explicitly selected local authoring file in a child process.
    # The bundled VM cannot safely perform native file I/O across Python's CRT.
    from plugin_tools import Ruby, DEFAULT_GAME
    if len(source.encode())>150000:raise ValueError('Arquivo Ruby excede 150 KB.')
    ruby=Ruby()
    ruby.load_source('module NordelunaOnline; class Error < StandardError; end; MAX_RESPONSE=524288; end','local editor support')
    ruby.load_source((DEFAULT_GAME/'Plugins/Nordeluna Online/002_JSON.rb').read_text(encoding='utf-8'),'JSON codec')
    ruby.load_source(source,'conteudo-online.rb')
    data=json.loads(ruby.evaluate('NordelunaOnline::JSON.dump(NORDELUNA_CONTENT)'))
    return validate_content(data)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-ruby',type=Path,required=True)
    args=parser.parse_args()
    try:print(json.dumps(read_ruby(args.read_ruby.read_text(encoding='utf-8-sig')),ensure_ascii=False))
    except Exception as error:
        print(str(error)[:2000],file=sys.stderr)
        sys.exit(1)
