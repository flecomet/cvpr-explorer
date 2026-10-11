"""Shared site code checked against this repository's own config and pipeline output."""
import json
import os
import re
import shutil
import subprocess

import pytest

import build_site
import config

# Fields build_site.build reads from every paper without a default.
REQUIRED = {
    "id", "title", "authors", "abstract", "pdf_link", "forum_link",
    "keywords", "tldr", "area", "decision", "track",
}

needs_data = pytest.mark.skipif(
    not (os.path.exists(config.PAPERS_PATH) and os.path.exists(config.LAYOUT_PATH)),
    reason="pipeline output not present",
)


@pytest.fixture(scope="module")
def data():
    with open(config.PAPERS_PATH) as f:
        papers = json.load(f)
    with open(config.LAYOUT_PATH) as f:
        layout = json.load(f)
    return papers, layout


@needs_data
def test_papers_have_every_field_build_site_reads(data):
    papers, _ = data
    missing = {k for p in papers for k in REQUIRED - p.keys()}
    assert not missing, f"papers lack {sorted(missing)}"
    assert len({p["id"] for p in papers}) == len(papers), "duplicate paper ids"
    assert all(p["title"] and p["abstract"] for p in papers)


@needs_data
def test_build_runs_on_this_repository_data(data):
    papers, layout = data
    core, details = build_site.build(papers, layout)
    assert core["meta"] == {"name": config.NAME, "n": len(papers)}
    assert len(details["abstract"]) == len(papers)
    assert all(core["nn"])


def test_rendered_page_script_parses(tmp_path):
    node = shutil.which("node")
    assert node, "Node is required to validate the page script"
    with open(build_site.TEMPLATE_PATH, encoding="utf-8") as f:
        page = build_site.render_index(f.read())
    scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
    assert scripts, "no inline script in the page"
    js = tmp_path / "page.js"
    js.write_text("\n".join(scripts), encoding="utf-8")
    result = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

# Evaluate the rendered production functions; startup is covered separately below.
AUTHOR_HARNESS = r"""
const assert = require('node:assert/strict');
class Element {
  constructor(tag='div') { this.tagName=tag.toUpperCase(); this.children=[]; this.listeners={}; this.value=''; this.style={}; this.dataset={theme:'dark'}; }
  append(...kids) { this.children.push(...kids); }
  replaceChildren(...kids) { this.children=kids; }
  addEventListener(name, fn) { this.listeners[name]=fn; }
  click() { this.listeners.click?.({stopPropagation(){}}); }
  focus() { document.activeElement=this; }
  blur() { document.activeElement=document.body; }
  select() {}
  querySelector() { return {remove(){}}; }
  setAttribute(name,value) { this[name]=String(value); }
}
const elements = new Map();
const document = {getElementById(id) { if (!elements.has(id)) elements.set(id,new Element()); return elements.get(id); }, createElement(tag) {return new Element(tag);}, documentElement:new Element(), body:new Element(), listeners:{}, addEventListener(k,f){this.listeners[k]=f;}};
document.activeElement=document.body;
const localStorage={getItem(){return null;},setItem(){}};
let location=new URL('http://localhost/');
const history={replaceState(a,b,url){location=new URL(url);}};
const calls=[];
const Plotly={restyle(...args){calls.push(['restyle',...args]);},relayout(...args){calls.push(['relayout',...args]);}};
const getComputedStyle=()=>({getPropertyValue:()=> '#aaa'});
const matchMedia=()=>({matches:false});
const navigator={};
const fixture = {
 id:['a','b','c','d'], title:['First','Second','Third','Mention'], x:[0,2,4,6],y:[0,3,2,7],c:[0,1,-1,0],
 dec:[0,0,0,0],track:[0,0,0,0],site:[0,0,0,0],area:[0,0,0,0], decisions:['poster'],tracks:['main'],sites:[''],areas:[''],
 clusters:{0:{name:'Topic A',n:2},1:{name:'Topic B',n:1},'-1':{name:'unclustered',n:1}}, nn:[[1],[0],[0],[0]],meta:{name:'Test'}
};
const details={authors:['Ada Lovelace, Émile Test, Ada Lovelace','Grace Hopper','ADA  LOVELACE, Grace Hopper','Other'],abstract:['','','','Ada Lovelace'],kw:[['keyword'],[],[],[]],tldr:['','','',''],pdf:['','','',''],forum:['','','','']};
function descendants(e) {return [e,...e.children.filter(k=>k instanceof Element).flatMap(descendants)];}
function text(e) {return (e.textContent||'')+e.children.map(k=>typeof k==='string'?k:text(k)).join('');}
function button(label) {return descendants(panel).find(e=>e.tagName==='BUTTON' && (e.textContent===label || e.ariaLabel===label));}
"""


def run_author_js(tmp_path, assertions):
    node = shutil.which('node')
    assert node, 'Node is required for author behavior tests'
    page = build_site.render_index(open(build_site.TEMPLATE_PATH, encoding='utf-8').read())
    script = re.findall(r'<script>(.*?)</script>', page, re.S)[0]
    functions = script.split('\ninitTheme();')[0]
    js = tmp_path / 'author-test.js'
    program = AUTHOR_HARNESS + '\n' + functions + '''
D=fixture; X=details; $("colorby").value="topic";
buildHaystack(); buildAuthorIndex();
plotEl._fullLayout={xaxis:{range:[-1,8]},yaxis:{range:[-1,8]}};
''' + assertions
    js.write_text("require('node:vm').runInNewContext(" + json.dumps(program) +
                  ", {require, URL, URLSearchParams, setTimeout, clearTimeout, console, process});", encoding='utf-8')
    result = subprocess.run([node, str(js)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_author_index(tmp_path):
    run_author_js(tmp_path, r'''
assert.equal(normalizeAuthor('  E\u0301mile   TEST '), 'émile test');
assert.equal(authorIndex.get('name:ada lovelace').papers.size,2);
assert.deepEqual([...authorMatches(['ada lovelace','Grace Hopper'])].sort(),[0,1,2]);
assert.equal(authorMatches(['unknown']).size,0);
assert.deepEqual(splitAuthors(' A, , B '),['A','B']);
''')


HOMONYM_DETAILS = r'''
X={...details,authors:['Wei Wang','Wei Wang','WEI WANG','Wei Wang'],author_details:[
 [{id:'neurips:101',name:'Wei Wang',institution:'University A'}],
 [{id:'neurips:202',name:'Wei Wang',institution:'University B'}],
 [{id:'neurips:101',name:'WEI WANG',institution:'University A'}],
 []
]};
buildAuthorIndex();
'''


def test_identified_homonyms_and_unverified_names_stay_separate(tmp_path):
    run_author_js(tmp_path, HOMONYM_DETAILS + r'''
setSearchScope('authors'); applySearch('wei');
assert.deepEqual([...matchSet].sort(),[0,1,2,3]);
assert.match(text(panel),/University A/); assert.match(text(panel),/University B/);
assert.match(text(panel),/identity not verified/i);
selectAuthor('neurips:101'); assert.deepEqual([...matchSet].sort(),[0,2]);
addAuthor('neurips:202'); assert.deepEqual([...matchSet].sort(),[0,1,2]);
removeAuthor('neurips:101'); assert.deepEqual([...matchSet],[1]);
selectAuthor('name:wei wang'); assert.deepEqual([...matchSet],[3]);
''')


AFFILIATION_DETAILS = r'''
X={...details,
 authors:['Caroline Wang','Grace Hopper','A. Third','Other'],
 author_details:[
  [{id:'neurips:161749',name:'Caroline Wang',institution:'UT Austin | Google DeepMind'}],
  [{id:'neurips:100',name:'Grace Hopper',institution:'US Navy'}],
  [],
  []
 ]};
D={...fixture,title:['ROTATE','Other Paper','Third','Mention']};
buildHaystack(); buildAuthorIndex();
'''


def test_search_matches_full_author_info(tmp_path):
    run_author_js(tmp_path, AFFILIATION_DETAILS + r'''
setQuery('deepmind');
assert.deepEqual([...matchSet],[0]);
setQuery('navy');
assert.deepEqual([...matchSet],[1]);
setQuery('161749');
assert.deepEqual([...matchSet],[0]);
setQuery('third');
assert.deepEqual([...matchSet],[2]);
''')


def test_author_search_matches_full_author_info(tmp_path):
    run_author_js(tmp_path, AFFILIATION_DETAILS + r'''
setSearchScope('authors'); applySearch('deepmind');
assert.deepEqual([...matchSet],[0]);
assert.match(text(panel),/Caroline Wang/);
assert.match(text(panel),/Google DeepMind/);
applySearch('161749');
assert.deepEqual([...matchSet],[0]);
assert.match(text(panel),/Caroline Wang/);
selectAuthor('neurips:161749'); assert.deepEqual([...matchSet],[0]);
''')


def test_paper_author_button_selects_its_identity(tmp_path):
    run_author_js(tmp_path, HOMONYM_DETAILS + r'''
selectPaper(1);
descendants(panel).find(e=>e.tagName==='BUTTON' && e.textContent==='Wei Wang').click();
assert.deepEqual([...matchSet],[1]);
selectPaper(3);
descendants(panel).find(e=>e.tagName==='BUTTON' && e.textContent==='Wei Wang').click();
assert.deepEqual([...matchSet],[3]);
assert.match(text(panel),/identity not verified/i);
''')


def test_author_identity_url_survives_loading_and_navigation(tmp_path):
    run_author_js(tmp_path, HOMONYM_DETAILS + r'''
const enriched=X;
X=null;
restoreUrl(new URLSearchParams('scope=authors&author-id=neurips%3A202&p=b'));
detailsLoaded(enriched);
assert.equal(selectedPaper,1); assert.deepEqual([...matchSet],[1]);
assert.equal(location.searchParams.get('author-id'),'neurips:202');
returnToAuthorResults(); addAuthor('neurips:101');
const shared=new URLSearchParams(location.search);
clearSelection(); restoreUrl(shared);
assert.deepEqual([...matchSet].sort(),[0,1,2]);
restoreUrl(new URLSearchParams('scope=authors&author=Wei+Wang'));
assert.deepEqual([...matchSet].sort(),[0,1,2,3]);
selectAuthor('name:wei wang');
assert.equal(location.searchParams.get('author-id'),'name:wei wang');
const unverifiedUrl=new URLSearchParams(location.search);
clearSelection(); restoreUrl(unverifiedUrl);
assert.deepEqual([...matchSet],[3]);
''')


def test_author_search(tmp_path):
    run_author_js(tmp_path, r'''
setSearchScope('authors'); applySearch('ada');
assert.deepEqual([...matchSet].sort(),[0,2]);
selectAuthor('Ada Lovelace'); addAuthor('Grace Hopper'); addAuthor('ADA LOVELACE');
assert.equal(selectedAuthors.length,2);
assert.deepEqual([...matchSet].sort(),[0,1,2]);
assert.match(text(panel),/3 matching papers/);
assert.match(text(panel),/unclustered: 1/);
assert.equal(descendants(panel).filter(e=>e.tagName==='LI' && e.tabIndex===0).length,3);
assert.deepEqual(calls.filter(c=>c[0]==='restyle' && 'selectedpoints' in c[2]).at(-1)[2].selectedpoints,[[0,2,1]]);
selectAuthor('unknown'); assert.equal(matchSet.size,0); assert.equal(button('Fit matching papers').disabled,true);
assert.match(text(panel),/No matching papers/);
removeAuthor('unknown'); assert.equal(matchSet,null);
applySearch('Émile'); button('Fit matching papers').click();
assert.ok(calls.at(-1)[2]['xaxis.range'][0]<0);
''')


def test_author_button(tmp_path):
    run_author_js(tmp_path, r'''
activeCluster=0; selectPaper(0);
button('Show papers by Ada Lovelace').click();
assert.deepEqual([...matchSet].sort(),[0,2]);
assert.equal(activeCluster,null); assert.equal(selectedPaper,-1);
assert.equal(searchScope,'authors'); assert.equal(query,'');
''')


def test_author_url(tmp_path):
    run_author_js(tmp_path, r'''
restoreUrl(new URLSearchParams('scope=authors&author=E%CC%81mile+Test&author=ÉMILE+TEST&author=Unknown&c=0&p=c&q=draft'));
assert.equal(selectedAuthors.length,2); assert.equal(activeCluster,null); assert.equal(selectedPaper,2);
assert.equal(location.searchParams.get('c'),null);
assert.equal(location.searchParams.getAll('author-id').length,2);
assert.equal(location.searchParams.get('p'),'c');
restoreUrl(new URLSearchParams('q=Ada&p=a'));
assert.equal(searchScope,'all'); assert.equal(query,'Ada'); assert.equal(selectedPaper,0);
''')


def test_author_navigation(tmp_path):
    run_author_js(tmp_path, r'''
wire(); selectAuthor('Ada Lovelace'); selectPaper(0); toggleSaved(0);
button('← Back to author results').click();
assert.equal(selectedPaper,-1); assert.equal(location.searchParams.get('p'),null);
assert.equal(matchSet.size,2);
showSaved(); selectPaper(0); button('keyword').click();
assert.equal(searchScope,'all'); assert.equal(selectedAuthors.length,0);
selectAuthor('Ada Lovelace'); selectPaper(0);
const escape=()=>document.listeners.keydown({key:'Escape'});
escape(); assert.equal(panelView,'authors');
applySearch('draft'); escape(); assert.equal(query,''); assert.equal(selectedAuthors.length,1);
escape(); assert.equal(selectedAuthors.length,0); escape(); assert.equal(searchScope,'all');
selectAuthor('Ada Lovelace'); selectCluster(1); assert.equal(searchScope,'all'); assert.equal(matchSet,null);
''')


def test_author_search_loading(tmp_path):
    run_author_js(tmp_path, r'''
X=null; restoreUrl(new URLSearchParams('scope=authors&author=Ada+Lovelace'));
assert.match(text(panel),/Loading author/); assert.equal(matchSet,null);
selectAuthor('Grace Hopper'); detailsLoaded(details);
assert.deepEqual([...matchSet],[1,2]);
assert.equal(selectedAuthors[0],'name:grace hopper');
X=null; detailsFailed(new Error('network failed'));
assert.match(text(panel),/Unable to load author/); assert.doesNotMatch(hits.textContent,/0 match/);
''')


def test_author_search_debounce_and_viewport(tmp_path):
    run_author_js(tmp_path, r'''
(async () => {
wire(); selectPaper(0);
search.value='stale'; search.listeners.input();
button('Show papers by Ada Lovelace').click();
await new Promise(resolve=>setTimeout(resolve,180));
assert.equal(query,''); assert.deepEqual([...matchSet].sort(),[0,2]);
assert.equal(calls.filter(c=>c[0]==='relayout').length,0);
selectPaper(0); search.value='grace'; search.listeners.input();
await new Promise(resolve=>setTimeout(resolve,180));
assert.equal(panelView,'authors'); assert.equal(selectedPaper,-1);
assert.equal(selectedAuthors[0],'name:ada lovelace'); assert.equal(matchSet.size,2);
assert.ok(button('Add Grace Hopper'));
})().catch(err=>{console.error(err);process.exitCode=1;});
''')


def test_author_search_counts_and_truncation(tmp_path):
    run_author_js(tmp_path, r'''
D={...fixture,id:Array.from({length:305},(_,i)=>String(i)),title:Array(305).fill('Paper'),x:Array(305).fill(1),y:Array(305).fill(2),c:Array(305).fill(-1)};
X={...details,authors:Array(305).fill('Ada Lovelace, Grace Hopper')};
buildAuthorIndex(); selectAuthor('Ada Lovelace'); addAuthor('Grace Hopper');
assert.equal(matchSet.size,305);
assert.match(text(panel),/unclustered: 305/);
assert.match(text(panel),/First 300 matching papers listed/);
assert.equal(descendants(panel).filter(e=>e.tagName==='LI' && e.tabIndex===0).length,300);
''')


def test_author_url_loading_exit_and_failure(tmp_path):
    run_author_js(tmp_path, r'''
X=null;
restoreUrl(new URLSearchParams('scope=authors&author=Unknown&p=a&c=1'));
assert.equal(selectedPaper,0); assert.equal(activeCluster,null);
detailsFailed(new Error('unavailable'));
assert.match(text(panel),/Unable to load abstract/);
assert.match(hits.textContent,/unavailable/);
clearSelection(); detailsLoaded(details);
assert.equal(searchScope,'all'); assert.equal(selectedAuthors.length,0); assert.equal(matchSet,null);
restoreUrl(new URLSearchParams('q=First&c=1'));
assert.equal(activeCluster,1); assert.equal(searchScope,'all'); assert.equal(query,'First');
assert.equal(location.searchParams.get('c'),'1');
''')


def test_author_url_preserves_topic_zero_after_exit(tmp_path):
    run_author_js(tmp_path, r'''
selectAuthor('Ada Lovelace'); selectCluster(0);
assert.equal(location.searchParams.get('c'),'0');
assert.equal(location.searchParams.get('scope'),null);
assert.equal(location.searchParams.getAll('author').length,0);
''')


def test_saved_duplicate_identifiers_migrate_to_one_paper(tmp_path):
    run_author_js(tmp_path, r'''
D.aliases={legacy:'a',older:'a'};
saved=['legacy','a','older','unavailable','b'];
migrateSavedIds();
assert.deepEqual(saved,['a','unavailable','b']);
showSaved();
assert.match(text(panel),/Saved papers \(2\)/);
''')


def test_old_paper_url_opens_current_paper(tmp_path):
    run_author_js(tmp_path, r'''
D.aliases={legacy:'a'};
restoreUrl(new URLSearchParams('p=legacy'));
assert.equal(selectedPaper,0);
assert.equal(location.searchParams.get('p'),'a');
''')
