from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlparse,parse_qs
from urllib.request import Request,urlopen
import hashlib,json,os,re
ROOT=os.path.dirname(os.path.abspath(__file__))
def analyze(u):
 p=urlparse(u)
 if p.scheme not in ("http","https"): raise ValueError("URL http/https requise")
 req=Request(u,headers={"User-Agent":"VerifiedContent/1.0"})
 with urlopen(req,timeout=12) as f:
  data=f.read(4*1024*1024); typ=f.headers.get_content_type(); final=f.geturl()
 domain=urlparse(final).netloc; h=hashlib.sha256(data).hexdigest()
 if typ.startswith("image/"):
  return {"badge":"🟡 Analyse technique disponible","cls":"yellow","rows":{"Domaine":domain,"Type":"Image","SHA-256":h,"Taille analysée":f"{len(data):,} octets","C2PA":"À intégrer","EXIF":"À intégrer","Signal IA":"À intégrer"},"note":"L’empreinte identifie cette copie, mais ne prouve pas à elle seule son authenticité."}
 text=data.decode("utf-8","ignore"); m=re.search(r"<title[^>]*>(.*?)</title>",text,re.I|re.S)
 title=re.sub(r"<[^>]+>"," ",m.group(1)).strip() if m else "Non détecté"
 return {"badge":"🟡 Source identifiable","cls":"yellow","rows":{"Domaine":domain,"Type":"Page / article","Titre":title[:300],"SHA-256":h,"Étape suivante":"Extraction des affirmations + comparaison indépendante"},"note":"La provenance d’une page et la véracité de ses affirmations sont deux choses différentes."}
class H(BaseHTTPRequestHandler):
 def send(self,c,t,b): self.send_response(c);self.send_header("Content-Type",t);self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path)
  if p.path=="/api/analyze":
   try:
    r=analyze(parse_qs(p.query).get("url",[""])[0]);self.send(200,"application/json; charset=utf-8",json.dumps(r,ensure_ascii=False).encode())
   except Exception as e:self.send(400,"application/json; charset=utf-8",json.dumps({"error":str(e)},ensure_ascii=False).encode())
   return
  f=os.path.join(ROOT,"index.html" if p.path=="/" else p.path.lstrip("/"))
  if not os.path.isfile(f):self.send(404,"text/plain",b"Not found");return
  t="text/html; charset=utf-8" if f.endswith(".html") else "application/javascript" if f.endswith(".js") else "application/json"
  self.send(200,t,open(f,"rb").read())
HTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8765'))), H).serve_forever()
