# Design statistics behind docs/model.md and model/stats/ (kept to reproduce them).
# Run from a working folder (WORK, default: the current directory) holding adm/
# (osmium extracts of the Côte d'Ivoire OpenStreetMap file, ivory-coast-latest.osm.pbf),
# st/places-CI.csv (an export of the N-Ways places), keys/ and out/ci/. The figures
# were produced with:
#   stats.py CI keys/ci-sp.geojson k keys/ci-cap.geojson out/ci
#   analyse.py out/ci '{"annex_m2":25,"attach_m":5,"hut_m2":0}'
#   places_areas.py ivory-coast out/ci suburb,quarter,neighbourhood,village,hamlet,locality
#   sample.sh CI ivory-coast ; national_areas.py ivory-coast out/ci 0.834 village,hamlet,quarter,neighbourhood,suburb,town,city,locality
#   abidjan_communes.py   (buildings per Abidjan commune, OSM admin_level 8)
import json, csv, collections
import os
S=os.environ.get('WORK', os.getcwd())
AB=['Marcory','Treichville','Koumassi','Le Plateau','Adjamé','Yopougon','Attécoubé','Cocody','Port-Bouët','Abobo']
polys=[]
for l in open(f'{S}/adm/ivory-coast.geojsonseq'):
    l=l.lstrip('\x1e').strip()
    if not l: continue
    f=json.loads(l); p=f['properties']
    if p.get('admin_level')=='8' and p.get('name') in AB:
        g=f['geometry']; ps=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
        xs=[c[0] for P in ps for c in P[0]]; ys=[c[1] for P in ps for c in P[0]]
        polys.append((p['name'],ps,(min(xs),min(ys),max(xs),max(ys))))
def pip(x,y,ps):
    for P in ps:
        ins=False
        for ring in P:
            n=len(ring); j=n-1
            for i in range(n):
                xi,yi=ring[i]; xj,yj=ring[j]
                if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi)+xi: ins=not ins
                j=i
        if ins: return True
    return False
cnt=collections.Counter(); area=collections.Counter()
for r in csv.DictReader(open(f'{S}/out/ci/cap-buildings.csv')):
    x,y=float(r['cx']),float(r['cy']); hit='(outside the 10 communes)'
    for n,ps,b in polys:
        if b[0]<=x<=b[2] and b[1]<=y<=b[3] and pip(x,y,ps): hit=n; break
    cnt[hit]+=1; area[hit]+=float(r['area'])
out=[{'commune':k,'buildings':v,'estCompounds':round(v*0.834),'footprintM2':round(area[k])} for k,v in cnt.most_common()]
json.dump(out, open(f'{S}/ci-work/abidjan-communes.json','w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=0))
