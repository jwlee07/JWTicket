import io
import base64
import matplotlib.pyplot as plt
from wordcloud import WordCloud

def clean_text(text):
    """텍스트 전처리를 수행합니다."""
    if not isinstance(text, str):
        return ""
    return text.strip()

def preprocess_text(texts):
    """여러 텍스트를 전처리하고 결합합니다."""
    return " ".join([clean_text(text) for text in texts if text])

def generate_wordcloud_image(text, wc_width=800, wc_height=800, fig_width=8, fig_height=8):
    """워드클라우드 이미지를 생성합니다."""
    if not text:
        return ""
        
    # 워드클라우드 생성
    wordcloud = WordCloud(
        font_path="/System/Library/Fonts/AppleSDGothicNeo.ttc",
        width=wc_width,
        height=wc_height,
        background_color="white"
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
    return format(num, ",d") 