"""Offline synthetic load only. Creates temporary accounts/SQLite, never touches production."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import secrets
import statistics
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]

def benchmark(source,players,iterations):
    sys.path.insert(0,str(source))
    spec=importlib.util.spec_from_file_location('benchmark_relay',source/'relay.py')
    relay=importlib.util.module_from_spec(spec);spec.loader.exec_module(relay)
    with tempfile.TemporaryDirectory(prefix='nordeluna-benchmark-') as temporary:
        store=relay.Store(str(Path(temporary)/'temporary.sqlite3'));sessions=[]
        try:
            for i in range(players):
                account=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32))
                store.handle(dict(protocol=1,action='account_register',account=account,nickname='Bench'+str(i)))
                sessions.append(store.handle(dict(protocol=1,action='map_join',account=account,profile={'name':'Bench'+str(i)},room='PRACA',build='benchmark')))
            def request(i,seq):
                return dict(protocol=1,action='map_update',token=sessions[i]['token'],chat_enabled=True,after=0,
                    chat_epoch=store.chat_epoch+':0',state=dict(map=39,x=i%20,y=i//20,seq=seq,direction=2,frame=0,moving=False,character='trainer_RED'))
            for i in range(players):store.handle(request(i,0))
            queries=[0]
            def count(statement):queries[0]+=1
            store.db.set_trace_callback(count);samples=[];raw_sizes=[];gzip_sizes=[];gzip_times=[]
            for n in range(iterations):
                started=time.perf_counter_ns();reply=store.handle(request(n%players,n+1))
                raw=json.dumps(reply,ensure_ascii=False,separators=(',',':')).encode()
                samples.append((time.perf_counter_ns()-started)/1e6)
                raw_sizes.append(len(raw));started=time.perf_counter_ns()
                gzip_sizes.append(len(gzip.compress(raw,compresslevel=1,mtime=0)))
                gzip_times.append((time.perf_counter_ns()-started)/1e6)
            return dict(players=players,packets=iterations,median_ms=round(statistics.median(samples),3),p95_ms=round(sorted(samples)[int(len(samples)*.95)],3),
                sql_per_packet=round(queries[0]/iterations,2),mean_json_bytes=round(statistics.mean(raw_sizes)),mean_gzip_bytes=round(statistics.mean(gzip_sizes)),gzip_median_ms=round(statistics.median(gzip_times),3))
        finally:store.db.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'server')
    parser.add_argument('--players',type=int,nargs='+',default=[2,40,150])
    parser.add_argument('--iterations',type=int,default=500)
    args=parser.parse_args()
    if not 20<=args.iterations<=10000 or any(not 1<=n<=500 for n in args.players):parser.error('Use 1..500 players and 20..10000 packets.')
    print(json.dumps([benchmark(args.source.resolve(),n,args.iterations) for n in args.players],indent=2))
