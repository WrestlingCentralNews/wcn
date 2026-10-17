import os,json,urllib.request,urllib.parse,sys
T=os.environ["YANDEX_WEBMASTER_TOKEN"];B="https://api.webmaster.yandex.net/v4"
def req(m,p,body=None):
    r=urllib.request.Request(B+p,method=m,headers={"Authorization":"OAuth "+T,"Content-Type":"application/json"},data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(r,timeout=20) as f: return f.status,json.loads(f.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code,e.read().decode()[:300]
s,u=req("GET","/user");print("user",s);uid=u["user_id"]
s,h=req("GET",f"/user/{uid}/hosts");print("hosts",s,[(x["host_id"],x.get("verified")) for x in h.get("hosts",[])])
hid=[x["host_id"] for x in h["hosts"] if "wrestlingcentralnews" in x["host_id"]][0]
s,sm=req("GET",f"/user/{uid}/hosts/{hid}/user-added-sitemaps");print("added",s,sm)
for url in ["https://wrestlingcentralnews.com/sitemap.xml","https://wrestlingcentralnews.com/es/sitemap.xml"]:
    print("add",url,req("POST",f"/user/{uid}/hosts/{hid}/user-added-sitemaps",{"url":url}))
s,sm=req("GET",f"/user/{uid}/hosts/{hid}/sitemaps");print("detected",s,sm)
