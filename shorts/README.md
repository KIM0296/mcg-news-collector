# 쇼츠 영상 자동 만들기

1. 브리프 플러그인이 만든 **쇼츠 대본 엑셀**(`MCG_Shorts_YYYYMMDD.xlsx`)을 내려받습니다.
2. 이 폴더(`shorts`) 화면에서 **Add file → Upload files**를 누르고 엑셀을 끌어다 놓은 뒤 **Commit changes**를 누릅니다.
3. 5~10분 뒤 저장소 오른쪽의 **Releases**에 `쇼츠 YYYYMMDD`가 생기고, 영상 5개(mp4)를 내려받을 수 있습니다.
   - 바로가기: https://github.com/KIM0296/mcg-news-collector/releases

- 자료 영상을 찾는 순서: ① `shorts_maker/assets/clips`의 MCG 자체 모음(파일 이름이 검색어와 맞는 것) ② Pixabay(Settings → Secrets의 `PIXABAY_API_KEY`) ③ Pexels(`PEXELS_API_KEY`) ④ 모두 없으면 남색 그라데이션 배경
- 배경음악: 저작권 걱정 없는 잔잔한 음악을 자동 합성합니다. 원하는 음악이 있으면 `shorts_maker/assets/bgm.mp3`로 올리면 그걸 씁니다(저작권 확인 필수).
