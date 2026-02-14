#!/usr/bin/env python3
"""
GEO Audit Tool - Otimização para Mecanismos de Resposta Generativa (GEO)
----------------------------------------------------------------------
Este script realiza uma auditoria técnica em sites para avaliar sua 
preparação para serem citados por IAs (como ChatGPT, Claude, Gemini).

Módulos de Análise (v2.0):
1. Acesso por Bots: Verifica permissões no robots.txt para bots de IA.
2. Estrutura Semântica: Valida hierarquia de headers (H1-H6) e legibilidade.
3. Schema.org: Validação avançada de EEAT em JSON-LD.
4. E-E-A-T: Análise de conteúdo, bio de autor e citações.
5. Entidades (NER): Densidade de entidades nomeadas e relevância tópica.
6. Main Content: Razão texto/HTML e isolamento do conteúdo principal.
7. Auditoria de Links: Verificação assíncrona de links e autoridade de domínio.
8. Performance: Tamanho da página e tempo de resposta.
9. Autoridade (Google): Mede autoridade via páginas indexadas (Scrapingdog).

Uso:
    python3 geo-audit.py https://exemplo.com.br
"""


import os                    # Interação com o sistema operacional (arquivos, variáveis de ambiente)
import sys                   # Acesso a parâmetros e configurações do interpretador Python
import asyncio               # Framework para programação assíncrona (concorrência e I/O não bloqueante)
import aiohttp              # Cliente HTTP assíncrono para realizar requisições de alta performance
import urllib.robotparser    # Parser nativo para interpretar regras do arquivo robots.txt
import json                  # Manipulação de dados (serialização/deserialização) no formato JSON
import re                    # Expressões Regulares para busca e manipulação avançada de texto
from datetime import datetime # Manipulação de datas e horários (timestamps, comparações de tempo)
from urllib.parse import urlparse, urljoin  # Parse (análise) e manipulação segura de URLs
from typing import Dict, Any, List, Optional, Tuple # Tipagem estática para melhor documentação e suporte de IDE

from collections import Counter # Estruturas de dados especializadas (utilizado para contagem de frequências)

from bs4 import BeautifulSoup, Tag # Biblioteca principal para parse e navegação em HTML/XML
# import spacy                  # (Desativado) Processamento de Linguagem Natural (NER, tokens)
import textstat              # Cálculo de estatísticas de texto (como índice de legibilidade Flesch)


# --- Versão ---
VERSION = "2.0.0"

# --- Configuração ---
USER_AGENT = 'Mozilla/5.0 (compatible; GEO-Audit-Bot/2.0)'
TIMEOUT_SECONDS = 15
MAX_RETRIES = 2

# Configurar idioma do textstat para português (aproximação)
textstat.set_lang('pt')


# Tentar importar Google Generative AI
HAS_GEMINI = False
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    pass

def analyze_with_gemini(data: Dict[str, Any]) -> Optional[str]:
    """
    Envia o resumo dos dados para o Gemini e retorna uma análise qualitativa.
    Requer a variável de ambiente GEMINI_API_KEY.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not HAS_GEMINI or not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash') # Modelo rápido e eficiente

        # Preparar prompt com dados resumidos
        summary = {
            "url": data['url'],
            "topic": data['topic_detected'],
            "score": data['geo_score'],
            "entities": [e[0] for e in data['details']['entities']['top_entities'][:5]],
            "main_content_ratio": data['details']['main_content']['text_to_html_ratio'],
            "flesch": data['details']['structure']['flesch_score'],
            "schema_types": data['details']['schema']['found_types'],
            "broken_links": data['details']['links']['broken_links_sample'],
            "indexed_pages": data['details']['authority'].get('indexed_pages', 'N/A')
        }

        prompt = f"""
        Atue como um Especialista Sênior em GEO (Generative Engine Optimization) e SEO Técnico.
        Analise os seguintes dados de auditoria de um site:
        {json.dumps(summary, indent=2)}

        Gere um relatório conciso, direto e estratégico (em Markdown) com:
        1. **Análise de Situação**: Opinião crítica sobre o estado atual (Entidades, Conteúdo, Técnico).
        2. **Números Ideais**: Para cada métrica fraca, estipule uma meta realista (ex: "Aumentar Ratio Texto/HTML para 20%").
        3. **Veredito Final**: Uma frase de impacto sobre a prontidão deste site para ser citado por IAs.

        Não repita os dados brutos. Foque em *insights* e *porquês*.
        Use emojis para destacar seções.
        """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro na análise via Gemini: {str(e)}"



# spaCy desabilitado temporariamente devido a incompatibilidade com Python 3.14 / Pydantic V1
HAS_SPACY = False
nlp = None
# try:
#     import spacy
#     ...
# except ...


# --- Utils Assíncronos ---

async def fetch_url(session: aiohttp.ClientSession, url: str, timeout: int = TIMEOUT_SECONDS) -> Optional[aiohttp.ClientResponse]:
    """Faz fetch de uma URL tratando erros básicos."""
    try:
        async with session.get(url, headers={'User-Agent': USER_AGENT}, timeout=timeout) as response:
            await response.read() # Garante que o conteúdo foi baixado
            return response
    except Exception:
        return None

async def get_page_content_async(url: str) -> Optional[bytes]:
    """Função principal para pegar o conteúdo da página alvo."""
    async with aiohttp.ClientSession() as session:
        response = await fetch_url(session, url)
        if response and response.status == 200:
            return response._body
    return None

# --- Módulo 1: Verificação de Acesso (Bots de IA) ---

async def check_robots_txt(url: str) -> Dict[str, Any]:
    """Verifica permissões para bots específicos de GEO."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(base, "robots.txt")
    
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(robots_url, timeout=TIMEOUT_SECONDS) as req:
                if req.status == 200:
                    text = await req.text()
                    rp.parse(text.splitlines())
                else:
                    return {"error": f"robots.txt returned {req.status}", "score_part": 0}
    except Exception:
        return {"error": "Could not fetch robots.txt", "score_part": 0}

    target_bots = [
        "GPTBot", "ClaudeBot", "PerplexityBot", "GoogleOther", "Applebot-Extended"
    ]
    
    results = {}
    score_impact = 0
    total_bots = len(target_bots)
    
    for bot in target_bots:
        allowed = rp.can_fetch(bot, url)
        results[bot] = allowed
        if allowed:
            score_impact += 1
            
    return {
        "details": results,
        "score_part": (score_impact / total_bots) * 100
    }

# --- Módulo 2: Estrutura Semântica e Legibilidade ---

def analyze_structure_and_readability(soup: BeautifulSoup) -> Dict[str, Any]:
    score_data = {
        "hierarchy_score": 0,
        "hierarchy_issues": [],
        "question_headers_count": 0,
        "answer_capsules_count": 0,
        "flesch_score": 0,
        "reading_difficulty": "N/A"
    }
    
    # 1. Validar Hierarquia H1 -> H6 (Sem saltos)
    headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    if not headers:
        score_data["hierarchy_issues"].append("No headers found")
    else:
        # Verificar H1 único
        h1s = [h for h in headers if h.name == 'h1']
        if len(h1s) == 1:
            score_data["hierarchy_score"] += 20
        elif len(h1s) == 0:
            score_data["hierarchy_issues"].append("Missing H1")
        else:
            score_data["hierarchy_issues"].append("Multiple H1s")
            
        # Verificar ordem lógica (ex: H1 -> H3 é proibido)
        last_level = 0
        for h in headers:
            current_level = int(h.name[1])
            if current_level > last_level + 1:
                # Permitir H1 -> H2, H2 -> H3 etc.
                # O primeiro header deve ser H1 (level 1). Se for H2 (2 > 0+1), ok se não tiver H1? Não, estrutura ruim.
                # Mas vamos ser pragmáticos: H1 -> H3 é salto. H2 -> H4 é salto.
                if last_level != 0: # Ignorar check no primeiro elemento se ele não for H1 (já pegamos erro acima)
                     score_data["hierarchy_issues"].append(f"Header Jump: H{last_level} -> H{current_level}")
            last_level = current_level

    # Pontuação de Hierarquia
    if not score_data["hierarchy_issues"]:
        score_data["hierarchy_score"] = 100 # Perfeito
    else:
        # Penaliza por erros, mas mantém base se tiver H1
        if "Missing H1" not in score_data["hierarchy_issues"] and "Multiple H1s" not in score_data["hierarchy_issues"]:
             score_data["hierarchy_score"] = max(40, 100 - (len(score_data["hierarchy_issues"]) * 10))
    
    # 2. Perguntas e Cápsulas
    question_starters = ['como', 'o que', 'por que', 'quando', 'onde', 'qual', 'quem', 'how', 'what', 'why', 'when', 'where', 'which', 'who']
    
    relevant_headers = [h for h in headers if h.name in ['h2', 'h3']]
    for header in relevant_headers:
        text = header.get_text().strip()
        is_question = text.endswith('?') or any(text.lower().startswith(q) for q in question_starters)
        
        if is_question:
            score_data["question_headers_count"] += 1
            # Verificar Cápsula
            next_node = header.next_sibling
            while next_node and (isinstance(next_node, str) or next_node.name not in ['p', 'div', 'section', 'h1','h2','h3','h4','h5','h6']):
                if isinstance(next_node, Tag) and next_node.name == 'p':
                    break
                next_node = next_node.next_sibling
                
            if next_node and isinstance(next_node, Tag) and next_node.name == 'p':
                words = next_node.get_text().split()
                if 40 <= len(words) <= 60:
                     score_data["answer_capsules_count"] += 1

    # 3. Legibilidade (Flesch Reading Ease)
    # Extrair texto do main content seria ideal, mas usaremos do body limpo
    text_content = ' '.join([p.get_text() for p in soup.find_all('p')])
    if text_content:
        # textstat entende português +- bem para contar sílabas
        score = textstat.flesch_reading_ease(text_content)
        score_data["flesch_score"] = score
        
        # Classificação Flesch (Pt-BR adaptado)
        if score >= 75: score_data["reading_difficulty"] = "Muito Fácil"
        elif score >= 50: score_data["reading_difficulty"] = "Fácil/Médio"
        elif score >= 25: score_data["reading_difficulty"] = "Difícil"
        else: score_data["reading_difficulty"] = "Muito Difícil (Acadêmico)"

    return score_data

# --- Módulo 3: Dados Estruturados (JSON-LD) Avançado ---

def analyze_schema_advanced(soup: BeautifulSoup) -> Dict[str, Any]:
    scripts = soup.find_all('script', type='application/ld+json')
    result = {
        "found_types": [],
        "eeat_errors": [],
        "score_part": 0
    }
    
    target_schemas = ['Organization', 'Person', 'FAQPage', 'Article', 'Product', 'BlogPosting', 'NewsArticle']
    
    for script in scripts:
        try:
            content = script.string
            if not content: continue
            data = json.loads(content)
            
            items = []
            if isinstance(data, list): items = data
            elif isinstance(data, dict):
                 if '@graph' in data: items = data['@graph']
                 else: items = [data]
            
            for item in items:
                s_type = item.get('@type')
                if isinstance(s_type, list): s_type = s_type[0] # as vezes vem lista
                
                if s_type in target_schemas:
                    result["found_types"].append(s_type)
                    
                    # Validação E-E-A-T
                    if s_type in ['Organization', 'Person']:
                        same_as = item.get('sameAs')
                        if not same_as:
                            result["eeat_errors"].append(f"{s_type} missing 'sameAs'")
                    
                    if s_type in ['Article', 'BlogPosting', 'NewsArticle']:
                        if 'author' not in item:
                            result["eeat_errors"].append(f"{s_type} missing 'author'")
                        else:
                            # Tentar validar author deep check
                            author = item['author']
                            if isinstance(author, dict) and ('sameAs' not in author and 'url' not in author):
                                 result["eeat_errors"].append(f"{s_type}.author missing 'sameAs' or 'url'")
                        
                        if 'dateModified' not in item:
                            result["eeat_errors"].append(f"{s_type} missing 'dateModified'")
                        
                        # Extra: reviewedBy
                        if 'reviewedBy' not in item:
                             pass # Não é erro crítico, mas seria bom
                             
        except json.JSONDecodeError:
            result["eeat_errors"].append("Invalid JSON-LD syntax")
        except Exception:
            continue

    result["found_types"] = list(set(result["found_types"]))
    
    # Pontuação Schema
    base_score = 0
    if result["found_types"]: base_score = 60
    # Bonus por tipos ricos
    if 'FAQPage' in result["found_types"]: base_score += 10
    if 'Article' in result["found_types"] or 'BlogPosting' in result["found_types"]: base_score += 10
    
    # Penalidade por erros
    penalty = len(result["eeat_errors"]) * 10
    result["score_part"] = max(0, min(100, base_score - penalty))
    
    return result

# --- Módulo 4: Link Audit & Autoridade (Async) ---

async def audit_links_and_authority(soup: BeautifulSoup, session: aiohttp.ClientSession, base_url: str) -> Dict[str, Any]:
    """Verifica todos os links externos e classifica autoridade."""
    links = soup.find_all('a', href=True)
    external_links = set()
    domain_auth_counts = {"gov": 0, "edu": 0, "org": 0, "generic": 0}
    
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc
    
    # Filtrar links externos
    for tag in links:
        href = tag['href']
        parsed = urlparse(href)
        if parsed.scheme in ['http', 'https'] and parsed.netloc and parsed.netloc != base_domain:
            external_links.add(href)
            
            # Classificação Básica
            if parsed.netloc.endswith('.gov') or parsed.netloc.endswith('.gov.br'):
                domain_auth_counts["gov"] += 1
            elif parsed.netloc.endswith('.edu') or parsed.netloc.endswith('.edu.br'):
                domain_auth_counts["edu"] += 1
            elif parsed.netloc.endswith('.org') or parsed.netloc.endswith('.org.br'):
                domain_auth_counts["org"] += 1
            else:
                domain_auth_counts["generic"] += 1

    # Verificar Top 20 Links Ext (para não demorar demais)
    target_links = list(external_links)[:20]
    broken_links = 0
    
    async def check_link(lnk):
        try:
            async with session.head(lnk, timeout=5, allow_redirects=True) as resp:
                if resp.status >= 400: return True
        except:
             # Tentar GET se HEAD falhar
            try:
                async with session.get(lnk, timeout=5) as resp:
                    if resp.status >= 400: return True
            except:
                return True # Considerar quebrado se exception
        return False

    results = await asyncio.gather(*[check_link(l) for l in target_links])
    broken_links = sum(results)
    
    return {
        "total_external_links": len(external_links),
        "broken_links_sample": broken_links,
        "sample_size": len(target_links),
        "authority_profile": domain_auth_counts,
        "score_part": 100 if broken_links == 0 else max(0, 100 - (broken_links * 10))
    }

# --- Módulo 5: Entidades (NER) ---


def analyze_entities(soup: BeautifulSoup, target_topic: str = "") -> Dict[str, Any]:
    """Extrai Top 10 Entidades (Via spaCy ou Fallback Regex) e compara com tópico."""
    text = soup.get_text(separator=' ', strip=True)
    
    top_10 = []
    
    if HAS_SPACY and nlp:
        try:
            doc = nlp(text[:100000]) # Limite char para performance
            # Contar Entidades (ORG, PER, LOC, MISC)
            ents = [e.text.lower() for e in doc.ents if e.label_ in ['ORG', 'PER', 'LOC', 'MISC'] and len(e.text) > 2]
            top_10 = Counter(ents).most_common(10)
        except Exception:
            # Fallback se der erro durante execução do nlp()
            pass
            
    # Fallback se spaCy não estiver disponível ou falhar
    if not top_10:
        # Heurística simples: Palavras com inicial maiúscula (que não sejam início de frase)
        # Regex simplificado para "Proper Nouns"
        # 1. Encontrar palavras com Título
        # 2. Ignorar palavras muito comuns de início de frase (ex: O, A, Em, Para...) - difícil sem lista, mas ok para fallback
        matches = re.findall(r'\b[A-Z][a-zà-ü]+\b', text)
        stop_words = {'Para', 'Com', 'Em', 'De', 'Do', 'Da', 'Um', 'Uma', 'Os', 'As', 'Ao', 'Na', 'No', 'Se', 'Por', 'Mas', 'Que', 'Como', 'Quando', 'Onde', 'Quem', 'Qual', 'Sobre', 'Entre', 'Ate', 'Desde'}
        filtered = [m.lower() for m in matches if len(m) > 2 and m not in stop_words]
        top_10 = Counter(filtered).most_common(10)
    
    # Match com Tópico
    is_relevant = False
    if target_topic:
        target_tokens = target_topic.lower().split()
        # Verificar se alguma parte do tópico está nas entidades
        for ent, count in top_10:
             if any(t in ent for t in target_tokens):
                 is_relevant = True
                 break
                 
    return {
        "top_entities": top_10,
        "topic_relevance": is_relevant if target_topic else "N/A",
        "method": "spaCy" if HAS_SPACY and nlp else "Regex Fallback"
    }


# --- Módulo 6: Main Content (MC) & Ratio ---

def extract_main_content(soup: BeautifulSoup) -> Dict[str, Any]:
    """Isola Main Content e calcula ratio."""
    # Remover boilerplate
    for tag in soup(['header', 'footer', 'nav', 'aside', 'script', 'style', 'iframe']):
        tag.decompose()
        
    # Tentar achar <main> ou <article>
    main_tag = soup.find('main') or soup.find('article')
    
    html_len = len(str(soup))
    
    if main_tag:
        text_content = main_tag.get_text(strip=True)
        mc_len = len(text_content)
    else:
        # Fallback para body
        body = soup.find('body')
        text_content = body.get_text(strip=True) if body else ""
        mc_len = len(text_content)
        
    ratio = (mc_len / html_len) * 100 if html_len > 0 else 0
    
    return {
        "has_semantic_main": bool(main_tag),
        "text_to_html_ratio": round(ratio, 2),
        "mc_length_chars": mc_len
    }

# --- Módulo 7: Scrapingdog (Autoridade) ---
def check_site_authority_sync(url):
    """(Wrapper Sincrono existente) - Poderia ser async mas requer reescrita completa da lógica interna complexa."""
    # Mantendo compatibilidade com a função antiga, mas poderia ser convertida.
    # Por simplicidade neste refactor, vamos rodar em thread separada ou manter sync rápido.
    # Vamos converter para usar requests.get normal já que é 1 chamada.
    
    api_key = os.environ.get('SCRAPINGDOG_API_KEY')
    if not api_key: return {"disabled": True}

    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    
    query = f"site:{domain}"
    google_domain = "google.com.br" if domain.endswith('.br') else "google.com"
    country = "br" if domain.endswith('.br') else "us"
    
    api_url = f"https://api.scrapingdog.com/google/?api_key={api_key}&query={query}&google_domain={google_domain}&country={country}&advance_search=true"
    
    try:
        import requests
        resp = requests.get(api_url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        
        search_info = data.get('search_information', {})
        total = search_info.get('total_results', 0)
        
        # Fallbacks
        if not total:
            meta = data.get('meta_data', {})
            total = meta.get('total_results', 0)
            
        organic = data.get('organic_results', [])
        
        return {
            "indexed_pages": total or 0,
            "top_results_count": len(organic),
            "domain": domain
        }
    except Exception as e:
        return {"error": str(e)}

async def check_authority_async(url):
    # Rodar em executor para não bloquear
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, check_site_authority_sync, url)


# --- ORQUESTRADOR PRINCIPAL ---

async def analyze_url(url: str):
    print(f"📥 Analisando {url} ...")
    
    # 1. Download Content
    content = await get_page_content_async(url)
    if not content:
        print("❌ Erro ao baixar a URL.")
        return None
        
    soup = BeautifulSoup(content, 'lxml') # LXML Parser
    
    # Extrair Tópico (Title ou H1) para NER
    intro_topic = soup.title.string if soup.title else ""
    if not intro_topic:
        h1 = soup.find('h1')
        if h1: intro_topic = h1.get_text()
    
    # 2. Executar Módulos em Paralelo onde possível
    # Robots
    task_robots = check_robots_txt(url)
    
    # Authority (Scrapingdog)
    task_auth = check_authority_async(url)
    
    # Link Checker (precisa de session prória)
    async with aiohttp.ClientSession() as session:
        link_audit_res = await audit_links_and_authority(soup, session, url)
        
    # Análises CPU-bound (BeautifulSoup/Spacy)
    # Teoricamente bloqueariam o loop, mas para scripts single-shot é aceitável não usar ProcessPool
    struct_res = analyze_structure_and_readability(soup)
    schema_res = analyze_schema_advanced(soup)
    mc_res = extract_main_content(soup)
    ner_res = analyze_entities(soup, intro_topic)
    
    robots_res = await task_robots
    auth_res = await task_auth
    
    # EEAT Básico (Mantido do anterior)
    eeat_res = analyze_eeat_basic(soup)
    
    # Page Size
    size_mb = len(content) / (1024 * 1024)
    size_res = {"size_mb": round(size_mb, 2), "is_under_limit": size_mb <= 2.0}


    # Calcular Score
    geo_score = calculate_final_score(robots_res, struct_res, schema_res, eeat_res, link_audit_res, mc_res)
    
    # Montar objeto final primeiro
    result_data = {
        "url": url,
        "geo_score": geo_score,
        "timestamp": datetime.now().isoformat(),
        "topic_detected": intro_topic,
        "details": {
            "robots": robots_res,
            "structure": struct_res,
            "schema": schema_res,
            "eeat": eeat_res,
            "links": link_audit_res,
            "main_content": mc_res,
            "entities": ner_res,
            "page_size": size_res,
            "authority": auth_res
        }
    }

    # 3. Análise Qualitativa via Gemini (se disponível)
    # Executada após ter todos os dados
    gemini_analysis = None
    if HAS_GEMINI and os.environ.get("GEMINI_API_KEY"):
        print(f"🤖 Solicitando análise qualitativa ao Gemini (pode levar alguns segundos)...")
        # Pode ser feito síncrono aqui pois é a última etapa e depende de todos os dados
        try:
            loop = asyncio.get_running_loop()
            gemini_analysis = await loop.run_in_executor(None, analyze_with_gemini, result_data)
        except Exception as e:
            gemini_analysis = f"Erro ao chamar Gemini: {e}"
            
    result_data["gemini_analysis"] = gemini_analysis
    
    return result_data

def analyze_eeat_basic(soup):
    # Versão simplificada do anterior, focada no texto
    text = soup.get_text()
    has_bio = bool(soup.find('a', href=re.compile(r'linkedin|orcid'))) or bool(re.search(r'(sobre o autor|about the author)', text, re.I))
    stats = len(re.findall(r'(\d+%)|(\d{2,})', text))
    return {"has_bio": has_bio, "stats_density": stats}

def calculate_final_score(robots, struct, schema, eeat, links, mc):
    # Pesos
    w_robots = 0.15
    w_struct = 0.20
    w_schema = 0.20
    w_links = 0.15
    w_mc = 0.15
    w_eeat = 0.15
    
    s_robots = robots.get("score_part", 0)
    s_struct = struct["hierarchy_score"]
    s_schema = schema["score_part"]
    s_links = links["score_part"]
    s_mc = 100 if mc["has_semantic_main"] and mc["text_to_html_ratio"] > 10 else 50
    s_eeat = 100 if eeat["has_bio"] and eeat["stats_density"] > 5 else 50
    
    final = (s_robots * w_robots) + (s_struct * w_struct) + (s_schema * w_schema) + \
            (s_links * w_links) + (s_mc * w_mc) + (s_eeat * w_eeat)
            
    return round(final, 1)

# --- CLI Report ---

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

def print_markdown(text):
    """Renderiza Markdown básico para terminal com cores."""
    if not text: return

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            print()
            continue
            
        # Headers (###, ##, #)
        if line.startswith('### '):
            print(f"\n{Colors.HEADER}{Colors.BOLD}{line[4:]}{Colors.ENDC}")
            continue
        if line.startswith('## '):
            print(f"\n{Colors.CYAN}{Colors.BOLD}{line[3:]}{Colors.ENDC}")
            continue
        if line.startswith('# '):
            print(f"\n{Colors.BLUE}{Colors.BOLD}{line[2:].upper()}{Colors.ENDC}")
            continue

        # Processar formatação inline (Bold)
        # Regex para **bold** -> mudando para cor amarela ou negrito
        line = re.sub(r'\*\*(.*?)\*\*', f'{Colors.BOLD}{Colors.WARNING}\\1{Colors.ENDC}', line)
        
        # Listas (* ou -)
        if line.startswith('* ') or line.startswith('- '):
            print(f"   {Colors.GREEN}•{Colors.ENDC} {line[2:]}")
        else:
            print(f"   {line}")


def generate_action_items(data):
    """Gera uma lista consolidada de ações baseada nos dados analisados."""
    d = data['details']
    actions = []
    
    # 1. Robots
    robots = d['robots']
    blocked = [k for k, v in robots['details'].items() if not v]
    if blocked:
        actions.append(f"🤖 Desbloquear bots de IA no robots.txt: {', '.join(blocked)}")
        
    # 2. Structure
    st = d['structure']
    if st['hierarchy_issues']:
        actions.append(f"🏗️  Corrigir hierarquia de headers: {', '.join(st['hierarchy_issues'])}")
    if st['question_headers_count'] == 0:
        actions.append("❓ Adicionar perguntas em H2/H3 para capturar intenção de busca (Voz/IA).")
    if st['flesch_score'] < 40:
        actions.append("📖 Simplificar o texto (Flesch muito baixo) para facilitar o processamento.")

    # 3. Schema
    sch = d['schema']
    if not sch['found_types']:
        actions.append("🧠 Implementar JSON-LD (Article, Organization, FAQPage).")
    else:
        for err in sch['eeat_errors']:
            actions.append(f"🔧 Schema Fix: {err}")
            
    # 4. Content
    mc = d['main_content']
    if mc['text_to_html_ratio'] < 10:
        actions.append("📄 Aumentar proporção de texto vs HTML (está abaixo de 10%). Reduzir scripts/boilerplate.")
        
    # 5. Entidades
    ner = d['entities']
    if not ner['topic_relevance']:
        actions.append("🎯 Otimizar conteúdo: As entidades principais não correspondem ao tópico detectado.")
        
    # 6. Links
    lnk = d['links']
    if lnk['broken_links_sample'] > 0:
        actions.append(f"🔗 Corrigir links quebrados (detectados {lnk['broken_links_sample']} na amostra).")
        
    # 7. Page Size
    pz = d['page_size']
    if not pz['is_under_limit']:
        actions.append(f"📦 Reduzir tamanho da página ({pz['size_mb']}MB > 2MB). Ideal para bots mobile/IA.")
        
    return actions

def print_report(data):
    d = data['details']
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}🔎 GEO Audit Report v{VERSION}{Colors.ENDC}")
    print(f"🔗 URL: {data['url']}")
    print(f"📝 Tópico Identificado: {data['topic_detected']}")
    print(f"📅 Data: {data['timestamp']}")
    
    # Score
    sc = data['geo_score']
    c_sc = Colors.GREEN if sc >= 80 else (Colors.WARNING if sc >= 50 else Colors.FAIL)
    print(f"\n{Colors.BOLD}🏆 GEO SCORE: {c_sc}{sc}/100{Colors.ENDC}")

    # 1. Entidades
    print(f"\n{Colors.HEADER}1. Análise de Entidades (NER & Tópico){Colors.ENDC}")
    ner = d['entities']
    status_topic = f"{Colors.GREEN}✅ Sim{Colors.ENDC}" if ner['topic_relevance'] else f"{Colors.FAIL}❌ Baixa Relevância{Colors.ENDC}"
    print(f"   Relevância Semântica: {status_topic}")
    print(f"   Top Entidades Encontradas:")
    if ner['top_entities']:
        for ent, count in ner['top_entities'][:5]:
            print(f"     - {ent:<20} : {count}x")
    else:
        print("     (Nenhuma entidade relevante detectada)")

    # 2. Main Content
    print(f"\n{Colors.HEADER}2. Main Content & Ratio{Colors.ENDC}")
    mc = d['main_content']
    ratio_color = Colors.GREEN if mc['text_to_html_ratio'] > 15 else Colors.WARNING
    print(f"   Tag Semântica <main> : {'✅ Sim' if mc['has_semantic_main'] else '❌ Não'}")
    print(f"   MC/HTML Ratio        : {ratio_color}{mc['text_to_html_ratio']}%{Colors.ENDC} (Ideal > 15%)")

    # 3. Structure
    print(f"\n{Colors.HEADER}3. Estrutura & Legibilidade{Colors.ENDC}")
    st = d['structure']
    print(f"   Hierarquia H1-H6     : {'✅ Ok' if st['hierarchy_score'] == 100 else '⚠️  Problemas'}")
    if st['hierarchy_issues']:
        print(f"     {Colors.FAIL}Issues: {', '.join(st['hierarchy_issues'])}{Colors.ENDC}")
    print(f"   Flesch Score         : {st['flesch_score']} ({st['reading_difficulty']})")
    print(f"   Perguntas (H2/H3)    : {st['question_headers_count']}")

    # 4. Schema
    print(f"\n{Colors.HEADER}4. Dados Estruturados (Schema & EEAT){Colors.ENDC}")
    sch = d['schema']
    print(f"   Tipos Detectados     : {', '.join(sch['found_types']) if sch['found_types'] else 'Nenhum'}")
    if sch['eeat_errors']:
        for err in sch['eeat_errors']:
             print(f"   ❌ {err}")
    else:
        if sch['found_types']:
            print(f"   ✅ Validação EEAT (SameAs/Author): OK")
        else:
            print(f"   ⚠️  Nenhum Schema para validar EEAT.")

    # 5. Links
    print(f"\n{Colors.HEADER}5. Links & Autoridade Externa{Colors.ENDC}")
    lnk = d['links']
    broken_c = lnk['broken_links_sample']
    broken_s = f"{Colors.FAIL}{broken_c}{Colors.ENDC}" if broken_c > 0 else f"{Colors.GREEN}0{Colors.ENDC}"
    print(f"   Links Quebrados      : {broken_s} (Amostra: {lnk['sample_size']})")
    
    profiles = []
    if lnk['authority_profile']['gov'] > 0: profiles.append(f"Gov: {lnk['authority_profile']['gov']}")
    if lnk['authority_profile']['edu'] > 0: profiles.append(f"Edu: {lnk['authority_profile']['edu']}")
    profile_str = ", ".join(profiles) if profiles else "Apenas genéricos"
    print(f"   Perfil de Autoridade : {profile_str}")
    
    # 6. Autoridade Site
    auth = d['authority']
    if not auth.get('disabled') and 'error' not in auth:
         print(f"\n{Colors.HEADER}6. Autoridade do Domínio (Google Index){Colors.ENDC}")
         print(f"   Páginas Indexadas    : {auth['indexed_pages']}")
         print(f"   Resultados Topo      : {auth['top_results_count']}")

    # GEMINI ANALYSIS
    if data.get("gemini_analysis"):
        print(f"\n{Colors.BOLD}{Colors.BLUE}🤖 ANÁLISE QUALITATIVA GEMINI (BETA){Colors.ENDC}")
        print("-" * 60)
        print_markdown(data["gemini_analysis"])
        print("-" * 60)

    # PLANO DE AÇÃO
    actions = generate_action_items(data)
    print(f"\n{Colors.BOLD}{Colors.WARNING}🚀 PLANO DE AÇÃO (PRIORITÁRIO){Colors.ENDC}")
    if not actions:
        print(f"   {Colors.GREEN}🎉 Nenhum problema crítico detectado. Seu site está bem otimizado para GEO!{Colors.ENDC}")
    else:
        for i, action in enumerate(actions, 1):
            print(f"   {i}. {action}")
            
    print("\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='GEO Audit Tool v2.0 - Otimização para IA Generativa')
    parser.add_argument('url', help='URL para auditar (ex: https://site.com.br)')
    args = parser.parse_args()
    
    url = args.url
    if not url.startswith('http'): url = 'https://' + url
    
    print(f"{Colors.BLUE}Inicializando auditoria GEO v{VERSION}...{Colors.ENDC}")
    try:
        data = asyncio.run(analyze_url(url))
        if data:
            print_report(data)
    except KeyboardInterrupt:
        print("\n\n🛑 Auditoria cancelada pelo usuário.")
    except Exception as e:
        print(f"\n{Colors.FAIL}Erro Fatal: {str(e)}{Colors.ENDC}")

if __name__ == "__main__":
    main()

