f=open('file.txt','r')
data=f.read()
for i in data.split('\n'):
    print(i)
f.close()