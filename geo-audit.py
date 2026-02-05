#!/Users/jandirp/scripts/.venv/bin/python3
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import urllib.robotparser
import json
import re
from datetime import datetime, timedelta

# --- Configuração ---
USER_AGENT = 'Mozilla/5.0 (compatible; GEO-Audit-Bot/1.0)'
TIMEOUT_SECONDS = 5
MAX_RETRIES = 2

def get_page_content(url):
    """Realiza a requisição HTTP com timeout e retry simples."""
    headers = {'User-Agent': USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        return None

# --- Módulo 1: Verificação de Acesso (Bots de IA) ---
def check_robots_txt(url):
    """Verifica permissões para bots específicos de GEO."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(base, "robots.txt")
    
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    
    try:
        # Simulando acesso rápido para evitar timeout padrão do urllib
        req = requests.get(robots_url, timeout=TIMEOUT_SECONDS)
        if req.status_code == 200:
            rp.parse(req.text.splitlines())
        else:
            return {"error": f"robots.txt returned {req.status_code}"}
    except Exception:
        return {"error": "Could not fetch robots.txt"}

    target_bots = [
        "GPTBot",           # OpenAI
        "ClaudeBot",        # Anthropic
        "PerplexityBot",    # Perplexity AI
        "GoogleOther",      # Google (geral para R&D/Internal)
        "Applebot-Extended" # Apple Intelligence
    ]
    
    results = {}
    score_impact = 0
    total_bots = len(target_bots)
    
    for bot in target_bots:
        allowed = rp.can_fetch(bot, url)
        # Verifica se especificamente Allow: / está presente (implícito se allowed=True mas vamos confiar no parser)
        results[bot] = allowed
        if allowed:
            score_impact += 1
            
    return {
        "details": results,
        "score_part": (score_impact / total_bots) * 100  # 100 se todos permitidos
    }

# --- Módulo 2: Análise Semântica e Estrutural ---
def analyze_structure(soup):
    score_data = {
        "hierarchy_score": 0,
        "question_headers_count": 0,
        "answer_capsules_count": 0,
        "fragment_anchors_count": 0,
        "issues": []
    }
    
    # 1. Validar Hierarquia H1 -> H2 -> H3
    h1s = soup.find_all('h1')
    h2s = soup.find_all('h2')
    h3s = soup.find_all('h3')
    
    if len(h1s) == 1:
        score_data["hierarchy_score"] += 20
    elif len(h1s) == 0:
        score_data["issues"].append("Missing H1")
    else:
        score_data["issues"].append("Multiple H1s")
        
    if h2s: score_data["hierarchy_score"] += 10
    if h3s: score_data["hierarchy_score"] += 10 # Bônus se tiver profundidade
    
    # 2. H2/H3 como Perguntas & 3. Cápsulas de Resposta
    question_starters = ['como', 'o que', 'por que', 'quando', 'onde', 'qual', 'quem', 'how', 'what', 'why', 'when', 'where', 'which', 'who']
    
    headers = h2s + h3s
    for header in headers:
        text = header.get_text().strip()
        is_question = text.endswith('?') or any(text.lower().startswith(q) for q in question_starters)
        
        if is_question:
            score_data["question_headers_count"] += 1
            
            # Verificar Cápsula de Resposta (Parágrafo seguinte 40-60 palavras)
            next_sib = header.find_next_sibling()
            while next_sib and next_sib.name not in ['p', 'div', 'section', 'h1','h2','h3','h4','h5','h6']: 
                # Pular comentários ou nav strings vazias
                next_sib = next_sib.find_next_sibling()
                
            if next_sib and next_sib.name == 'p':
                words = next_sib.get_text().split()
                if 40 <= len(words) <= 60:
                    score_data["answer_capsules_count"] += 1
    
    # 4. Âncoras de Fragmento (IDs únicos em seções)
    sections = soup.find_all(['section', 'div'])
    for sec in sections:
        # Verifica se tem um H2 filho direto (aproximação)
        if sec.find('h2', recursive=False) and sec.get('id'):
            score_data["fragment_anchors_count"] += 1

    return score_data

# --- Módulo 3: Dados Estruturados (JSON-LD) ---
def analyze_schema(soup):
    scripts = soup.find_all('script', type='application/ld+json')
    result = {
        "found_types": [],
        "entity_links_valid": False,
        "freshness_valid": False,
        "score_part": 0
    }
    
    target_schemas = ['Organization', 'Person', 'FAQPage', 'Article', 'Product']
    
    for script in scripts:
        try:
            data = json.loads(script.string)
            if not isinstance(data, list):
                if '@graph' in data:
                    data = data['@graph']
                else:
                    data = [data]
            
            for item in data:
                s_type = item.get('@type')
                if s_type in target_schemas:
                    result["found_types"].append(s_type)
                    
                # Entity Linking (SameAs)
                if s_type in ['Organization', 'Person']:
                    same_as = item.get('sameAs', [])
                    if isinstance(same_as, str): same_as = [same_as]
                    for link in same_as:
                        if 'wikidata.org' in link or 'google.com/search' in link: # Knowledge Graph URL approx
                             result["entity_links_valid"] = True
                             
                # Freshness (Article)
                if s_type == 'Article' and 'dateModified' in item:
                    try:
                        dm_str = item['dateModified'].replace('Z', '+00:00')
                        # Tentar lidar com ISO 8601 básico
                        dm_date = datetime.fromisoformat(dm_str)
                        if (datetime.now(dm_date.tzinfo) - dm_date).days < 90:
                            result["freshness_valid"] = True
                    except:
                        pass # Falha no parse da data
                        
        except:
            continue
            
    # Pontuação Parcial Schema
    if result["found_types"]: result["score_part"] += 40
    if result["entity_links_valid"]: result["score_part"] += 30
    if result["freshness_valid"]: result["score_part"] += 30
    
    result["found_types"] = list(set(result["found_types"]))
    return result

# --- Módulo 4: Performance e E-E-A-T ---
def analyze_eeat(soup):
    result = {
        "has_author_bio": False,
        "citation_count": 0,
        "stats_density": 0,
        "score_part": 0
    }
    
    text_content = soup.get_text()
    
    # 1. Sinais de Autor
    # Procura links para LinkedIn/ORCID ou seções de "Sobre/Author"
    links = soup.find_all('a', href=True)
    for link in links:
        href = link['href'].lower()
        if 'linkedin.com/in' in href or 'orcid.org' in href:
            result["has_author_bio"] = True
            break
            
    # Fallback: Procura string "Sobre o Autor" ou similar próximo ao fim
    if not result["has_author_bio"]:
        if re.search(r'(sobre o autor|about the author|escrito por|written by)', text_content, re.IGNORECASE):
            result["has_author_bio"] = True

    # 2. Dados Fatuais (Citações Externas + Estatísticas)
    # Contar links externos no body (excluindo nav/footer seria ideal, mas simplificando)
    external_links = 0
    domain = "" # TBD: extrair do contexto se possivel, aqui estamos sem o dominio original no soup fn
    for link in links:
        href = link['href']
        if href.startswith('http') and 'facebook' not in href and 'twitter' not in href: # Simple filter
             external_links += 1
    result["citation_count"] = external_links
    
    # Contar números e porcentagens
    # Regex para % e números significativos (ignora pontuação 1-10 solta)
    stats_matches = re.findall(r'(\d+%)|(\d{2,})', text_content)
    result["stats_density"] = len(stats_matches)
    
    # Pontuação Simples
    if result["has_author_bio"]: result["score_part"] += 30
    if result["stats_density"] > 5: result["score_part"] += 30 # Arbitrário: >5 dados numéricos relevantes
    if result["citation_count"] > 2: result["score_part"] += 40 # Citações externas
    
    return result

# --- Orquestrador ---
def calculate_geo_score(robots, structure, schema, eeat):
    # Pesos Arbitrários para compor o GEO Score (0-100)
    w_robots = 0.20
    w_struct = 0.25
    w_schema = 0.30
    w_eeat = 0.25
    
    s_robots = robots.get("score_part", 0)
    
    # Structure Score calc
    s_struct = structure["hierarchy_score"] # Max 40
    if structure["question_headers_count"] > 0: s_struct += 20
    if structure["answer_capsules_count"] > 0: s_struct += 20
    if structure["fragment_anchors_count"] > 0: s_struct += 20
    s_struct = min(100, s_struct)
    
    s_schema = schema["score_part"]
    s_eeat = eeat["score_part"]
    
    final_score = (s_robots * w_robots) + (s_struct * w_struct) + (s_schema * w_schema) + (s_eeat * w_eeat)
    return round(final_score, 1)

def generate_recommendations(robots, structure, schema, eeat):
    recs = []
    
    # Robots
    blocked = [k for k,v in robots.get("details", {}).items() if not v]
    if blocked:
        recs.append(f"CRÍTICO: Desbloqueie os seguintes bots no robots.txt: {', '.join(blocked)}")
        
    # Structure
    if structure["hierarchy_score"] < 40:
        recs.append("Melhore a hierarquia H1/H2/H3. Garanta um único H1 e uso lógico de H2/H3.")
    if structure["question_headers_count"] == 0:
        recs.append("Use perguntas em tags H2/H3 (ex: 'O que é...?') para capturar intenção de busca.")
    if structure["answer_capsules_count"] == 0:
        recs.append("Crie 'Cápsulas de Resposta': parágrafos de 40-60 palavras logo após um H2/H3.")
    if structure["fragment_anchors_count"] == 0:
        recs.append("Adicione IDs únicos em <section> ou <div> para permitir deep-linking pela IA.")
        
    # Schema
    if not schema["found_types"]:
        recs.append("Implemente JSON-LD para Organization, Article ou Product.")
    if schema["found_types"] and not schema["entity_links_valid"]:
        recs.append("Adicione 'sameAs' apontando para Wikidata/KnowledgeGraph no seu Schema Organization/Person.")
        
    # EEAT
    if not eeat["has_author_bio"]:
        recs.append("Adicione uma biografia de autor clara com links para LinkedIn/ORCID para validar autoridade.")
    if eeat["stats_density"] < 3:
        recs.append("Enriqueça o conteúdo com dados estatísticos (%, números) para aumentar a confiabilidade factual.")

    return recs

# --- Formatação CLI ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_cli_report(data):
    def color_bool(val, true_text="✅ Sim", false_text="❌ Não"):
        return f"{Colors.GREEN}{true_text}{Colors.ENDC}" if val else f"{Colors.FAIL}{false_text}{Colors.ENDC}"

    def header(text):
        print(f"\n{Colors.HEADER}{Colors.BOLD}=== {text} ==={Colors.ENDC}")

    url = data['url']
    score = data['geo_score']
    
    # Cabeçalho Principal
    print(f"\n{Colors.BOLD}{Colors.CYAN}🔎 RELATÓRIO DE GEO (Generative Engine Optimization){Colors.ENDC}")
    print(f"🔗 Alvo: {Colors.UNDERLINE}{url}{Colors.ENDC}")
    print(f"📅 Data: {data['timestamp']}")
    
    # Score
    score_color = Colors.GREEN if score >= 80 else (Colors.WARNING if score >= 50 else Colors.FAIL)
    print(f"\n{Colors.BOLD}🏆 GEO SCORE GERAL: {score_color}{score}/100{Colors.ENDC}")

    # 1. Acesso (Bots)
    header("1. Acesso de Robôs (robots.txt)")
    access = data['details']['access']
    if 'error' in access:
        print(f"{Colors.FAIL}Erro: {access['error']}{Colors.ENDC}")
    else:
        details = access.get('details', {})
        # Agrupar visualmente
        print(f"   Status Global: {color_bool(access.get('score_part', 0) == 100, 'Tudo Liberado', 'Restrições Encontradas')}")
        for bot, allowed in details.items():
            status = f"{Colors.GREEN}ALLOWED{Colors.ENDC}" if allowed else f"{Colors.FAIL}BLOCKED{Colors.ENDC}"
            print(f"   • {bot:<20} : {status}")

    # 2. Estrutura
    header("2. Estrutura & Semântica")
    struct = data['details']['structure']
    print(f"   • Hierarquia H1-H3     : {color_bool(struct['hierarchy_score'] >= 20, 'Boa', 'Precisa Melhorar')}")
    print(f"   • Headers de Pergunta  : {struct['question_headers_count']} encontrados")
    print(f"   • Cápsulas de Resposta : {struct['answer_capsules_count']} (Blocos de 40-60 palavras pós-header)")
    print(f"   • Âncoras Profundas    : {struct['fragment_anchors_count']} seções com ID")
    
    if struct['issues']:
        print(f"   ⚠️  Problemas: {', '.join(struct['issues'])}")

    # 3. Schema
    header("3. Dados Estruturados (JSON-LD)")
    schema = data['details']['schema']
    types = schema['found_types']
    print(f"   • Tipos Relevantes     : {', '.join(types) if types else 'Nenhum'}")
    print(f"   • Entity Links (SameAs): {color_bool(schema['entity_links_valid'])}")
    print(f"   • Conteúdo Recente     : {color_bool(schema['freshness_valid'])}")

    # 4. E-E-A-T
    header("4. E-E-A-T & Credibilidade")
    eeat = data['details']['eeat']
    print(f"   • Identificação Autor  : {color_bool(eeat['has_author_bio'])}")
    print(f"   • Densidade Estatística: {eeat['stats_density']} dados (números/%)")
    print(f"   • Citações Externas    : {eeat['citation_count']} links")

    # Recomendações
    print(f"\n{Colors.BOLD}{Colors.WARNING}🔧 RECOMENDAÇÕES PRIORITÁRIAS:{Colors.ENDC}")
    if not data['prioritized_recommendations']:
        print(f"   {Colors.GREEN}Nenhuma recomendação crítica. Ótimo trabalho!{Colors.ENDC}")
    else:
        for i, rec in enumerate(data['prioritized_recommendations'], 1):
            print(f"   {i}. {rec}")
    print("\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Auditoria GEO para Sites')
    parser.add_argument('url', help='URL do site para analisar')
    parser.add_argument('--json', action='store_true', help='Output em formato JSON puro')
    args = parser.parse_args()

    url = args.url
    if not url.startswith('http'): url = 'https://' + url
    
    response = get_page_content(url)
    if not response:
        err = {"error": "Failed to fetch URL"}
        if args.json:
            print(json.dumps(err))
        else:
            print(f"{Colors.FAIL}Erro fatal: Não foi possível acessar a URL {url}{Colors.ENDC}")
        sys.exit(1)
        
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Análises
    robots_res = check_robots_txt(url)
    struct_res = analyze_structure(soup)
    schema_res = analyze_schema(soup)
    eeat_res = analyze_eeat(soup)
    
    # Score Final
    geo_score = calculate_geo_score(robots_res, struct_res, schema_res, eeat_res)
    recommendations = generate_recommendations(robots_res, struct_res, schema_res, eeat_res)
    
    output = {
        "url": url,
        "geo_score": geo_score,
        "timestamp": datetime.now().isoformat(),
        "details": {
            "access": robots_res,
            "structure": struct_res,
            "schema": schema_res,
            "eeat": eeat_res
        },
        "prioritized_recommendations": recommendations
    }
    
    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print_cli_report(output)

if __name__ == "__main__":
    main()
