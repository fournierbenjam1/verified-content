from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlparse,parse_qs
from urllib.request import Request,urlopen
import hashlib,json,os,re,html

ROOT=os.path.dirname(os.path.abspath(__file__))

def analyze(url):
    p=urlparse(url)
    if p.scheme not in ('http','https'): raise ValueError('L’URL doit commencer par http:// ou https://')
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 VerifiedContent/1.0'})
    with urlopen(req,timeout=15) as f:
        data=f.read(8*1024*1024)
        content_type=f.headers.get_content_type()
        final_url=f.geturl()
    domain=urlparse(final_url).netloc
    digest=hashlib.sha256(data).hexdigest()
    if content_type.startswith('image/'):
        return {'badge':'🟡 Analyse technique disponible','rows':{
        'Domaine':domain,'Type':'Image','URL finale':final_url,
        'Empreinte SHA-256':digest,'Taille récupérée':f'{len(data):,} octets',
        'EXIF':'À analyser dans la prochaine version','C2PA':'À analyser dans la prochaine version',
        'Signaux IA':'À analyser dans la prochaine version'},
        'note':'Cette empreinte correspond à la copie récupérée à cette URL. Elle ne prouve pas à elle seule que l’image est authentique.'}
    text=data.decode('utf-8','ignore')
    # Extraction simple du contenu textuel
    clean=re.sub(r'<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>', ' ', text, flags=re.I|re.S)
    clean=re.sub(r'<[^>]+>', ' ', clean)
    clean=html.unescape(re.sub(r'\s+', ' ', clean)).strip()
    paragraphs=[x.strip() for x in re.split(r'(?<=[.!?])\s+', clean) if len(x.strip())>45]
    claims=[]
    patterns=[r'\b\d+(?:[.,]\d+)?\s*%', r'\b(?:toujours|jamais|meilleur|sans danger|prouvé|garantit|obligatoire|doit)\b']
    for sentence in paragraphs:
        if any(re.search(pat,sentence,re.I) for pat in patterns): claims.append(sentence[:300])
    claims=claims[:8]
    m=re.search(r'<title[^>]*>(.*?)</title>',text,re.I|re.S)
    title=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',m.group(1))).strip() if m else 'Titre non détecté'
    badge='🟡 Source identifiable' if claims else '⚪ Vérifiabilité limitée'
    rows={'Domaine':domain,'Type':'Page ou article','URL finale':final_url,'Titre':title[:400],'Empreinte SHA-256 de la réponse':digest,'Texte extrait':f'{len(clean):,} caractères','Affirmations à vérifier':len(claims)}
    for i,c in enumerate(claims,1): rows[f'Affirmation {i}']=c
    return {'badge':badge,'rows':rows,'note':'Cette analyse repère des éléments à vérifier. Elle ne constitue pas un verdict vrai/faux et la provenance d’une page ne prouve pas la véracité de ses affirmations.'}

class Handler(BaseHTTPRequestHandler):
    def send(self,code,ctype,body):
        self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        p=urlparse(self.path)
        if p.path=='/api/analyze':
            try:
                url=parse_qs(p.query).get('url',[''])[0]
                result=analyze(url)
                self.send(200,'application/json; charset=utf-8',json.dumps(result,ensure_ascii=False).encode())
            except Exception as e:
                self.send(400,'application/json; charset=utf-8',json.dumps({'error':str(e)},ensure_ascii=False).encode())
            return
        filename='index.html' if p.path=='/' else p.path.lstrip('/')
        path=os.path.join(ROOT,filename)
        if not os.path.isfile(path): self.send(404,'text/plain',b'Not found'); return
        ctype='text/html; charset=utf-8' if filename.endswith('.html') else 'application/javascript'
        self.send(200,ctype,open(path,'rb').read())
    def log_message(self,*args): pass

print('Verified Content ouvert sur http://127.0.0.1:8765')
HTTPServer(('0.0.0.0',int(os.environ.get('PORT','8765'))),Handler).serve_forever()
