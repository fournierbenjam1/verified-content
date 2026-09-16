from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from urllib.request import Request,urlopen
import hashlib,json,os,re,html

ROOT=os.path.dirname(os.path.abspath(__file__))

BOILERPLATE=re.compile(r'^(?:par\s+[^.]{2,80}\s+)?(?:le\s+\d{1,2}\s+\w+\s+\d{4}|\d{1,2}[/:]\d{1,2}(?:\s+\d{2}:\d{2})?)\s*',re.I)

def clean_sentence(s):
    s=html.unescape(re.sub(r'\s+',' ',s)).strip(' -–—:;')
    s=re.sub(r'^(?:[A-ZÀ-ÖØ-Ý][\wÀ-ÿ-]+\s+){1,4}(?:\d{1,2}\s+\w+\s+\d{4}\s+\d{1,2}:\d{2})\s*','',s)
    s=re.sub(r'^(?:publié|mis à jour|par)\s*[^.]{0,100}[.]\s*','',s,flags=re.I)
    return s.strip(' -–—:;')

def is_useful_claim(s):
    low=s.lower()
    if len(s)<65 or len(s)>420: return False
    if any(x in low for x in ['cookies','newsletter','abonnez','facebook','instagram','copyright','tous droits']): return False
    # A claim should contain a subject + assertion, not merely a heading or fragment.
    verbs=r'\b(?:est|sont|n’est|n\'est|peut|peuvent|permet|permettent|faut|doit|doivent|évite|éviter|conseille|recommande|recommandé|contient|nécessite|suffit|risque|garantit|favorise|provoque|rend|apporte|utiliser|préparer|cuire|décortiquer)\b'
    return bool(re.search(verbs,s,re.I)) and bool(re.search(r'[.!?]$',s))

def meta_value(text, names):
    for name in names:
        patterns = [
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\'](.*?)["\']',
            rf'<meta[^>]+content=["\'](.*?)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']'
        ]
        for pattern in patterns:
            m=re.search(pattern,text,re.I|re.S)
            if m:
                value=html.unescape(re.sub(r'<[^>]+>',' ',m.group(1))).strip()
                if value: return re.sub(r'\s+',' ',value)
    return ''

def classify_claim(s):
    low=s.lower()
    if any(x in low for x in ['toujours','jamais','la meilleure','le meilleur','sans danger','garantit','100 %','100%']):
        return '🟠', 'Formulation très générale ou subjective : elle demande une vérification.'
    if any(x in low for x in ['doit','faut','il est nécessaire','recommande','conseille','arroser','cuire','préparer','décortiquer']):
        return '🟡', 'Conseil ou recommandation : son intérêt dépend du contexte et de la méthode.'
    if re.search(r'\b\d+(?:[.,]\d+)?\s*(?:%|euros?|€|jours?|heures?|minutes?|cm|kg|g)\b', low):
        return '🟡', 'Donnée précise à confirmer avec une source ou une méthode fiable.'
    return '🟢', 'Information formulée de manière vérifiable, à comparer avec des sources indépendantes.'

def analyze(url):
    p=urlparse(url)
    if p.scheme not in ('http','https'): raise ValueError('L’URL doit commencer par http:// ou https://')
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 VerifiedContent/1.0'})
    with urlopen(req,timeout=8) as f:
        data=f.read(8*1024*1024); content_type=f.headers.get_content_type(); final_url=f.geturl()
    domain=urlparse(final_url).netloc; digest=hashlib.sha256(data).hexdigest()
    if content_type.startswith('image/'):
        return {'badge':'🟡 Analyse technique disponible','rows':{'Domaine':domain,'Type':'Image','URL finale':final_url,'Empreinte SHA-256':digest,'Taille récupérée':f'{len(data):,} octets','EXIF':'À analyser dans une prochaine version','C2PA':'À analyser dans une prochaine version','Signaux IA':'À analyser dans une prochaine version'},'note':'Cette empreinte correspond à la copie récupérée à cette URL. Elle ne prouve pas à elle seule que l’image est authentique.'}
    text=data.decode('utf-8','ignore')
    m=re.search(r'<title[^>]*>(.*?)</title>',text,re.I|re.S)
    title=clean_sentence(re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',m.group(1))).strip()) if m else 'Titre non détecté'
    author=meta_value(text,['author','article:author','parsely-author','byl']) or 'Auteur non identifié'
    date=meta_value(text,['article:published_time','datePublished','date','pubdate','parsely-pub-date']) or 'Date non identifiée'
    date=re.sub(r'T.*$','',date).strip()
    clean=re.sub(r'<(script|style|nav|header|footer|aside|form|button|noscript)[^>]*>.*?</\1>', ' ', text, flags=re.I|re.S)
    clean=re.sub(r'<[^>]+>',' ',clean); clean=html.unescape(re.sub(r'\s+',' ',clean)).strip()
    raw_sentences=re.split(r'(?<=[.!?])\s+',clean)
    candidates=[]; seen=set()
    for raw in raw_sentences:
        s=clean_sentence(raw)
        if is_useful_claim(s):
            key=re.sub(r'\W+',' ',s.lower()).strip()
            if key not in seen:
                seen.add(key); candidates.append(s)
    candidates.sort(key=lambda s: (bool(re.search(r'\b\d+(?:[.,]\d+)?\s*%|\b(?:toujours|jamais|doit|faut|peut|permet|risque|recommande|conseille)\b',s,re.I)), len(s)), reverse=True)
    claims=candidates[:6]
    summary=' '.join([clean_sentence(x) for x in raw_sentences if len(clean_sentence(x))>90][:3])[:900]
    if not summary: summary='Résumé automatique limité : le contenu principal n’a pas pu être isolé avec suffisamment de fiabilité.'
    rows={'Domaine':domain,'Type':'Page ou article','URL finale':final_url,'Titre':title[:400],'Auteur':author[:250],'Date de publication':date[:100],'Résumé de l’article':summary,'Empreinte SHA-256 de la réponse':digest,'Texte extrait':f'{len(clean):,} caractères','Affirmations détectées':len(claims)}
    for i,c in enumerate(claims,1):
        level, explanation=classify_claim(c)
        rows[f'Affirmation {i}']=f'{level} « {c} » → {explanation}'
    return {'badge':'🟡 Source identifiable' if claims else '⚪ Vérifiabilité limitée','rows':rows,'note':'Les affirmations sont des informations reformulées sous forme courte à partir de phrases complètes extraites de la page. Elles ne constituent pas encore un verdict vrai/faux : chaque affirmation doit être comparée à des sources indépendantes.'}


class Handler(BaseHTTPRequestHandler):
    def send(self,code,ctype,body):
        self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Content-Length',str(len(body))); self.send_header('Connection','close'); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        p=urlparse(self.path)
        if p.path=='/api/analyze':
            try:
                url=parse_qs(p.query).get('url',[''])[0]; result=analyze(url)
                self.send(200,'application/json; charset=utf-8',json.dumps(result,ensure_ascii=False).encode())
            except Exception as e: self.send(400,'application/json; charset=utf-8',json.dumps({'error':str(e)},ensure_ascii=False).encode())
            return
        filename='index.html' if p.path=='/' else p.path.lstrip('/'); path=os.path.join(ROOT,filename)
        if not os.path.isfile(path): self.send(404,'text/plain',b'Not found'); return
        ctype='text/html; charset=utf-8' if filename.endswith('.html') else 'application/javascript'; self.send(200,ctype,open(path,'rb').read())
    def log_message(self,*args): pass

print('Verified Content ouvert sur http://127.0.0.1:8765')
ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8765'))),Handler).serve_forever()
