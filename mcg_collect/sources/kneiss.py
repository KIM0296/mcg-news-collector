"""K-NEISS(한국원전수출산업협회 원전수출정보지원시스템) '세계원전시장동향' 해외 단신 수집 — 설정 대기.

기존 엑셀의 '해외 단신'(NucNet, Platts, ARPA-E, 기업 보도자료 등을 한국어로 요약한 기사)이
이곳에서 온 것으로 보인다. 아래 두 가지가 확인되면 이 파일만 채우면 된다.

  1) 출처가 K-NEISS '세계원전시장동향'이 맞는지 (다른 곳이면 그 게시판 주소)
  2) 로그인이 필요한지 → 필요하면 MCG 계정을 환경변수 KNEISS_ID / KNEISS_PW 로 넣는다
     (계정 정보는 코드나 엑셀에 적지 않는다)

채워야 할 함수: collect(fetcher, start, end, log) -> list[Item]
  - Item(category="해외단신", date="YYYY.MM.DD", media=원 매체명(NucNet 등), title=한국어 제목,
         url=원문 링크(없으면 K-NEISS 게시물 링크), keywords=본문 요약, country=관련국가, source="K-NEISS")
"""


class SourceNotConfigured(Exception):
    pass


def collect(fetcher, start, end, log=print):
    raise SourceNotConfigured("K-NEISS 수집은 출처·로그인 여부 확인 후 활성화됩니다 (지금은 건너뜀)")
