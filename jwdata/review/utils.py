import io
import base64
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from konlpy.tag import Okt
import re

# 불용어 리스트 정의
stop_words = [
    # 일반적인 불용어
    '이', '것', '그', '저', '거', '요', '는', '들', '님', '음', '는데', '에서', '으로',
    '에게', '뿐', '의', '가', '이다', '인', '듯', '고', '와', '한', '하다', '을', '를',
    '에', '의', '으로', '자', '에게', '뿐', '등', '및', '이랑', '까지', '부터', '도', '더',
    '너무', '많이', '많고', '적은', '적고', '없는', '없고', '있는', '있고', '몹시',
    '아주', '가장', '다소', '약간', '거의', '너무나', '되게', '무척', '워낙', '하도',
    '꽤', '상당히', '썩', '퍽', '몹시', '심히', '아주', '몰라', '모르', '그저', '그냥',
    '막', '되게', '개', '클래스', '급', '수준', '정도', '만큼', '것', '거', '거든',
    
    # 감정/감상 관련 일반 단어
    '정말', '너무', '진짜', '완전', '넘', '약간', '조금', '매우', '굉장히', '참', '되게',
    '많이', '엄청', '대박', '최고', '짱', '역대', '처음', '다시', '또', '계속', '쭉',
    '잘', '더', '많은', '많고', '적은', '적고', '없는', '없고', '있는', '있고', '몹시',
    '아주', '가장', '다소', '약간', '거의', '너무나', '되게', '무척', '워낙', '하도',
    '꽤', '상당히', '썩', '퍽', '몹시', '심히', '아주', '몰라', '모르', '그저', '그냥',
    '막', '되게', '개', '클래스', '급', '수준', '정도', '만큼', 
    
    # 공연 관련 일반 단어
    '공연', '연극', '뮤지컬', '콘서트', '배우', '연기', '관람', '보고', '봤는데', '봤어요',
    '작품', '무대', '극장', '공연장', '객석', '좌석', '표', '예매', '티켓', '공연시간',
    '시간', '분', '막', '관객', '출연', '캐스트', '공연날', '날짜', '회차', '내용',
    '스토리', '장면', '넘버', '노래', '연출', '대사', '연기력', '감동', '재미', '감상',
    '보면서', '보니', '봐서', '봤다', '보다', '보고', '본', '극', '공연', '공연을',
    '공연이', '공연의', '보러', '보기', '보게', '봐야', '봤습니다', '봤어요', '보았습니다',
    
    # 평가 관련 단어
    '좋다', '좋은', '좋았다', '좋았어요', '별로', '그냥', '괜찮다', '괜찮은', '최고',
    '대박', '실망', '아쉽다', '아쉬운', '기대', '추천', '비추', '후기', '리뷰', '평가',
    '최고다', '최고의', '최고였다', '최고예요', '최고입니다', '대박이다', '대박이에요',
    '실망이다', '실망스럽다', '아쉽다', '아쉬워요', '별로다', '별로예요', '그냥저냥',
    
    # 기타 자주 등장하는 불필요한 단어
    '사람', '생각', '느낌', '때문', '같은', '같다', '이런', '저런', '어떤', '이번',
    '저번', '다음', '지금', '요즘', '올해', '작년', '이상', '이하', '앞', '뒤',
    '위', '아래', '중', '내내', '제가', '저는', '나는', '우리', '오늘', '어제',
    '하나', '둘', '셋', '첫', '두', '세', '네', '다섯', '이게', '그게', '저게',
    '뭔가', '어떻게', '어찌', '이렇게', '그렇게', '저렇게', '이래', '그래', '저래',
    '이와', '그와', '저와', '이런', '그런', '저런'

    # 공연명
    '바닷마을 다이어리', '붉은 낙엽', '타인의 삶', '라이카', '바닷마을', '고스트 베이커리', 
    '긴긴밤', '무명, 준희', '테일러', '재패니메이션', '한스 짐머', '히사이시 조'
]

def clean_text(text):
    """텍스트 전처리를 수행합니다."""
    if not isinstance(text, str):
        return ""
    # 특수문자 제거 및 공백 정리
    cleaned = re.sub(r"[^가-힣a-zA-Z0-9\s]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def preprocess_text(texts):
    """여러 텍스트를 전처리하고 결합합니다."""
    okt = Okt()
    all_nouns = []

    for text in texts:
        if not text:
            continue
            
        # 텍스트 정제
        cleaned = clean_text(text)
        
        # 명사 추출
        nouns = okt.nouns(cleaned)
        
        # 불용어 제거 및 2글자 이상 단어만 선택
        filtered_nouns = [noun for noun in nouns if noun not in stop_words and len(noun) >= 2]
        
        all_nouns.extend(filtered_nouns)

    return " ".join(all_nouns)

def generate_wordcloud_image(text, wc_width=800, wc_height=800, fig_width=8, fig_height=8):
    """워드클라우드 이미지를 생성합니다."""
    if not text:
        return ""
        
    # 워드클라우드 생성
    wordcloud = WordCloud(
        font_path="/System/Library/Fonts/AppleSDGothicNeo.ttc",
        width=wc_width,
        height=wc_height,
        background_color="white",
        stopwords=stop_words  # 워드클라우드에도 불용어 적용
    ).generate(text)
    
    # 이미지로 변환
    plt.figure(figsize=(fig_width, fig_height))
    plt.imshow(wordcloud, interpolation="bilinear")
    plt.axis("off")
    
    # 이미지를 base64로 인코딩
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0)
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    plt.close()
    
    return base64.b64encode(image_png).decode()

def comma_format(num):
    """숫자를 천 단위 구분자가 있는 문자열로 변환합니다."""
    if not num:
        return "0"
    return format(num, ",d") 