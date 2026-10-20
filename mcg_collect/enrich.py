"""관련국가 추정 + 중복 제거.

관련국가는 제목·요약에 나오는 국가명으로 추정한다(정확하지 않으면 빈칸).
핵심 키워드는 일부러 비워 둔다 → GPT가 STEP 0에서 제목·원문 요약으로 채운다.
"""
import re

from .model import normalize_url

# (찾을 말, 국가) — 위에서부터 먼저 맞는 것 사용
COUNTRY_RULES = [
    # 한자 약칭 (국내 기사 제목)
    (r"美|미국|US\b|U\.S\.|USA|United States|American|Texas|Kentucky|New Jersey|Arkansas|California|Ohio|"
     r"Tennessee|Wyoming|Idaho|NRC\b|DOE\b|ARPA-E|Westinghouse|NuScale|TerraPower|X-energy|Oklo", "미국"),
    (r"中|중국|China|Chinese|CGN|CNNC|Hualong", "중국"),
    (r"日|일본|Japan|Japanese|TEPCO|Kansai", "일본"),
    (r"佛|프랑스|France|French|EDF\b|Orano|Framatome", "프랑스"),
    (r"英|영국|UK\b|U\.K\.|Britain|British|England|Scotland|Wales|Sizewell|Hinkley|Urenco|Capenhurst|"
     r"Rolls-Royce SMR", "영국"),
    (r"獨|독일|Germany|German", "독일"),
    (r"露|러시아|Russia|Russian|Rosatom|Rostekhnadzor|Kursk|Leningrad", "러시아"),
    (r"체코|Czech|CEZ|Dukovany|Temelin", "체코"),
    (r"폴란드|Poland|Polish", "폴란드"),
    (r"캐나다|Canada|Canadian|Ontario|OPG\b|Darlington|Bruce", "캐나다"),
    (r"인도|India|Indian|Kudankulam|NPCIL|AERB", "인도"),
    (r"베트남|Vietnam|Viet Nam|Ninh Thuan|닌투언", "베트남"),
    (r"사우디|Saudi", "사우디아라비아"),
    (r"UAE|아랍에미리트|Barakah|바라카", "UAE"),
    (r"튀르키예|터키|Turkey|Türkiye|Akkuyu|아쿠유", "튀르키예"),
    (r"카자흐|Kazakh", "카자흐스탄"),
    (r"방글라데시|Bangladesh|Rooppur", "방글라데시"),
    (r"스웨덴|Sweden|Swedish|Blykalla|Vattenfall", "스웨덴"),
    (r"노르웨이|Norw", "노르웨이"),
    (r"핀란드|Finland|Finnish|Onkalo|온칼로", "핀란드"),
    (r"스페인|Spain|Spanish", "스페인"),
    (r"이탈리아|Ital", "이탈리아"),
    (r"네덜란드|Netherlands|Dutch", "네덜란드"),
    (r"슬로바키아|Slovak|Mochovce", "슬로바키아"),
    (r"헝가리|Hungar|Paks", "헝가리"),
    (r"루마니아|Romania", "루마니아"),
    (r"불가리아|Bulgaria", "불가리아"),
    (r"우크라이나|Ukrain", "우크라이나"),
    (r"아일랜드|Ireland|Irish", "아일랜드"),
    (r"대만|Taiwan", "대만"),
    (r"필리핀|Philippin", "필리핀"),
    (r"인도네시아|Indonesia", "인도네시아"),
    (r"이집트|Egypt|El Dabaa", "이집트"),
    (r"남아공|South Africa", "남아프리카공화국"),
    (r"호주|Australia", "호주"),
    (r"브라질|Brazil", "브라질"),
    (r"아르헨티나|Argentin", "아르헨티나"),
    (r"벨기에|Belgi|Doel|Tihange", "벨기에"),
    (r"스위스|Switzerland|Swiss", "스위스"),
    (r"슬로베니아|Sloven|Krško|Krsko", "슬로베니아"),
    (r"아르메니아|Armenia", "아르메니아"),
    (r"우즈베키스탄|Uzbek", "우즈베키스탄"),
    (r"몽골|Mongolia", "몽골"),
    (r"태국|Thailand", "태국"),
    (r"말레이시아|Malaysia", "말레이시아"),
    (r"싱가포르|Singapore", "싱가포르"),
    (r"가나|Ghana", "가나"),
    (r"케냐|Kenya", "케냐"),
    (r"이란|Iran\b", "이란"),
    (r"북한|North Korea|DPRK", "북한"),
    (r"멕시코|Mexic", "멕시코"),
    (r"EU\b|유럽연합|European Commission|European Union", "EU"),
    (r"IAEA|국제원자력기구", "국제기구"),
    (r"韓|한국|Korea|KHNP|한수원|KEPCO|한전", "한국"),
]
_COMPILED = [(re.compile(p), c) for p, c in COUNTRY_RULES]


def guess_country(item):
    text = f"{item.title} {item.summary}"
    for rx, c in _COMPILED:
        if rx.search(text):
            return c
    if item.category in ("국내기사", "사설/칼럼/기고"):
        return "한국"
    return ""


def dedupe(items, log=print):
    """같은 링크는 1건만 남긴다. WNN 직접 수집본(요약 있음)을 KAIF 재게재본보다 우선."""
    order = {"WNN": 0, "K-NEISS": 1, "KAIF": 2}
    best = {}
    for it in sorted(items, key=lambda i: order.get(i.source, 9)):
        k = it.key()
        if k not in best:
            best[k] = it
        else:
            kept = best[k]
            # KAIF에만 있는 한국어 제목은 참고로 남긴다
            if it.source == "KAIF" and kept.source == "WNN" and it.title != kept.title:
                kept.extra["kaif_title"] = it.title
    removed = len(items) - len(best)
    if removed:
        log(f"  중복 링크 {removed}건 제거")
    return list(best.values())
