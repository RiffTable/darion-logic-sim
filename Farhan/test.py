import json
from Gates import Gate,AND,Nothing

a=AND()
a.code=(0,)
b=AND()
b.code=(2,)
l=set(a,b)
with open('test.json','w') as file:
    json.dump(l,file)