#!/usr/bin/env python3
"""
GEO Audit Tool - Otimização para Mecanismos de Resposta Generativa (GEO)
----------------------------------------------------------------------
Este script realiza uma auditoria técnica em sites para avaliar sua 
preparação para serem citados por IAs (como ChatGPT, Claude, Gemini).

Módulos de Análise:
1. Acesso por Bots: Verifica permissões no robots.txt para bots de IA.
2. Estrutura Semântica: Valida hierarquia de headers e cápsulas de resposta.
3. Schema.org: Detecta marcações estruturadas (FAQ, Article, Product).
4. E-E-A-T: Analisa sinais de Experiência, Especialidade, Autoridade e Confiança.
5. Tamanho da Página: Alerta sobre páginas muito pesadas para análise de IA.
6. Autoridade (Google): Mede autoridade via páginas indexadas (Scrapingdog).

Uso:
    python3 geo-audit.py https://exemplo.com.br
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import urllib.robotparser
import json
import re
from datetime import datetime, timedelta

# --- Versão ---
VERSION = "1.2.0"

# --- Configuração ---
USER_AGENT = 'Mozilla/5.0 (compatible; GEO-Audit-Bot/1.0)'
TIMEOUT_SECONDS = 15 # Aumentado para lidar com APIs externas
MAX_RETRIES = 2

def load_env():
    """Carrega variáveis de ambiente de um arquivo .env manual para evitar dependências extras."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip().strip('"').strip("'")

load_env()

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

# --- Módulo 5: Análise de Performance (Tamanho da Página) ---
def analyze_page_size(response):
    """Calcula o tamanho da página em MB."""
    size_bytes = len(response.content)
    size_mb = size_bytes / (1024 * 1024)
    
    return {
        "size_mb": round(size_mb, 2),
        "is_under_limit": size_mb <= 2.0
    }

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
    
    # Authority Score part (Bônus ou impacto)
    final_score = (s_robots * w_robots) + (s_struct * w_struct) + (s_schema * w_schema) + (s_eeat * w_eeat)
    return round(final_score, 1)

# --- Módulo 6: Autoridade do Site (Scrapingdog) ---
def check_site_authority(url):
    """Extrai informações de autoridade via Scrapingdog API."""
    api_key = os.environ.get('SCRAPINGDOG_API_KEY')
    if not api_key:
        return {"disabled": True}

    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith('www.'):
        domain = domain[4:]

    query = f"site:{domain}"
    
    # Parâmetros de localização para domínios .br ou gerais
    google_domain = "google.com.br" if domain.endswith('.br') else "google.com"
    country = "br" if domain.endswith('.br') else "us"
    
    api_url = (
        f"https://api.scrapingdog.com/google/?"
        f"api_key={api_key}&query={query}&google_domain={google_domain}"
        f"&country={country}&advance_search=true"
    )
    
    try:
        response = requests.get(api_url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        
        # O Scrapingdog retorna informações em search_information ou meta_data
        search_info = data.get('search_information', {})
        total_results = search_info.get('total_results')
        
        # Simular "keywords no topo" e fallback para total_results
        organic = data.get('organic_results', [])
        top_results_count = len(organic)

        if total_results is None or total_results == 0:
            # Fallback 1: Verificar meta_data
            meta = data.get('meta_data', {})
            total_results = meta.get('total_results')
            
            # Fallback 2: Se ainda for 0 mas houver resultados orgânicos, usamos o count local
            if (total_results is None or total_results == 0) and top_results_count > 0:
                total_results = top_results_count
            elif total_results is None:
                total_results = 0

        return {
            "indexed_pages": total_results,
            "top_results_count": top_results_count,
            "domain": domain
        }
    except Exception as e:
        return {"error": f"Erro na API Scrapingdog: {str(e)}"}

def generate_recommendations(robots, structure, schema, eeat, page_size, authority):
    recs = []
    
    # Authority
    if authority.get('disabled'):
        pass # Autoridade ignorada se chave não estiver presente
    elif 'error' in authority:
        recs.append(f"AVISO: Não foi possível verificar autoridade: {authority['error']}")
    elif authority.get('indexed_pages', 0) < 10:
        recs.append("Baixo número de páginas indexadas. Aumente a produção de conteúdo para ganhar autoridade perante a IA.")

    # Page Size
    if not page_size["is_under_limit"]:
        recs.append(f"CRÍTICO: O tamanho da página ({page_size['size_mb']}MB) excede o limite recomendado de 2MB. Páginas muito grandes dificultam a análise por mecanismos de IA.")

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
    page_size = data['details'].get('page_size', {})
    
    # Cabeçalho Principal
    print(f"\n{Colors.BOLD}{Colors.CYAN}🔎 RELATÓRIO DE GEO (Generative Engine Optimization) v{VERSION}{Colors.ENDC}")
    print(f"🔗 Alvo: {Colors.UNDERLINE}{url}{Colors.ENDC}")
    print(f"📅 Data: {data['timestamp']}")
    
    # Score & Size
    score_color = Colors.GREEN if score >= 80 else (Colors.WARNING if score >= 50 else Colors.FAIL)
    print(f"\n{Colors.BOLD}🏆 GEO SCORE GERAL: {score_color}{score}/100{Colors.ENDC}")
    
    if page_size:
        size_color = Colors.GREEN if page_size['is_under_limit'] else Colors.FAIL
        print(f"{Colors.BOLD}📦 TAMANHO DA PÁGINA: {size_color}{page_size['size_mb']} MB{Colors.ENDC}")

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

    # 5. Autoridade
    auth = data['details']['authority']
    if not auth.get('disabled'):
        header("5. Autoridade do Site (Scrapingdog)")
        if 'error' in auth:
            print(f"   {Colors.WARNING}⚠️  {auth['error']}{Colors.ENDC}")
        else:
            print(f"   • Domínio              : {auth['domain']}")
            print(f"   • Páginas Indexadas    : {auth['indexed_pages']:,}")
            print(f"   • Resultados no Topo   : {auth['top_results_count']} (Amostra da 1ª página)")

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
    parser = argparse.ArgumentParser(
        description='🚀 GEO Audit Tool - Auditoria de Otimização para mecanismos de resposta por IA.',
        epilog='Exemplo: python3 geo-audit.py https://netexperts.com.br'
    )
    parser.add_argument('url', help='URL do site para analisar')
    parser.add_argument('--json', action='store_true', help='Output em formato JSON puro para integrações')
    parser.add_argument('-v','--versao', '--version', action='version', version=f'%(prog)s {VERSION}')
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
    size_res = analyze_page_size(response)
    auth_res = check_site_authority(url)
    
    # Score Final
    geo_score = calculate_geo_score(robots_res, struct_res, schema_res, eeat_res)
    recommendations = generate_recommendations(robots_res, struct_res, schema_res, eeat_res, size_res, auth_res)
    
    output = {
        "url": url,
        "geo_score": geo_score,
        "timestamp": datetime.now().isoformat(),
        "details": {
            "access": robots_res,
            "structure": struct_res,
            "schema": schema_res,
            "eeat": eeat_res,
            "page_size": size_res,
            "authority": auth_res
        },
        "prioritized_recommendations": recommendations
    }
    
    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print_cli_report(output)

if __name__ == "__main__":
    main()
