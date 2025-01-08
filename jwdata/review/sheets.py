from django.http import HttpResponse
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from .models import Concert, Review, Seat

GOOGLE_SHEET_KEY = "1eEZ6wB2UyeJXbDjH0g2FlIXFUazP0QztjmBGyTs_NTs"  # 스프레드시트 키

def get_gspread_client():
    """
    구글 스프레드시트 클라이언트 객체를 생성해 반환하는 헬퍼 함수.
    """

    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive',
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        'ts-ticket-data-599d02f2629e.json',
        scope
    )

    return gspread.authorize(creds)

def open_ts_ticket_sheet():
    """
    "티켓스퀘어" 관련 구글 스프레드시트(위 KEY) 열기
    """
    client = get_gspread_client()
    spreadsheet = client.open_by_key(GOOGLE_SHEET_KEY)
    return spreadsheet

def get_worksheet(sheet_name):
    """
    sheet_name(예: concerts, reviews, seats)에 해당하는 worksheet를 반환
    """
    ss = open_ts_ticket_sheet()
    return ss.worksheet(sheet_name)

def create_concert_in_sheet(concert: Concert):
    """
    Concert 모델 인스턴스를 받아, 
    concerts 시트에 새 행을 추가(CREATE)하는 함수.
    """
    ws = get_worksheet("concerts")

    # DB pk가 아직 없다면 save()로 먼저 생성(또는 임의 PK 사용)
    if not concert.pk:
        concert.save()  # db에서 pk 할당

    # 시트에 들어갈 행 데이터
    # [id, name, place, start_date, end_date, duration_minutes]
    row_data = [
        concert.pk,
        concert.name,
        concert.place,
        str(concert.start_date) if concert.start_date else "",
        str(concert.end_date) if concert.end_date else "",
        str(concert.duration_minutes) if concert.duration_minutes else "",
    ]

    # 시트 맨 아래에 새로운 행 추가
    ws.append_row(row_data, value_input_option="RAW")

def read_all_concerts_from_sheet():
    """
    concerts 시트에서 모든 행을 읽어 파이썬 dict 리스트로 반환.
    """
    ws = get_worksheet("concerts")
    # 헤더 포함 전체 데이터를 가져옴
    all_values = ws.get_all_values()  

    # 첫 행을 헤더로 가정
    header = all_values[0]  # ['id', 'name', 'place', ...]
    data_rows = all_values[1:]  # 실제 데이터

    # 각 행을 dict로 변환
    concerts_data = []
    for row in data_rows:
        if not row:
            continue
        row_dict = {}
        for i, col_name in enumerate(header):
            # 인덱스 넘어서는 경우 빈 문자열 처리
            row_dict[col_name] = row[i] if i < len(row) else ""
        concerts_data.append(row_dict)

    return concerts_data

def update_concert_in_sheet(concert: Concert):
    """
    Concert 인스턴스의 pk(=id)와 동일한 id를 가진 시트 행을 찾아서
    나머지 컬럼 값들을 수정(UPDATE)한다.
    """
    ws = get_worksheet("concerts")
    # 시트 전체 rows 불러오기 (list of lists)
    all_values = ws.get_all_values()  

    # 첫 줄은 헤더이므로 실제 데이터는 2행부터 시작
    # "id" 열이 첫 번째(A열)라고 가정
    for idx, row in enumerate(all_values[1:], start=2):  # 2행부터
        sheet_id = row[0]
        if sheet_id == str(concert.pk):
            # 해당 행을 찾았으므로 업데이트할 range 결정
            # 예: A{idx} ~ F{idx}
            # A열 ~ F열 (Concert는 6컬럼)
            row_data = [
                str(concert.pk),
                concert.name,
                concert.place,
                str(concert.start_date) if concert.start_date else "",
                str(concert.end_date) if concert.end_date else "",
                str(concert.duration_minutes) if concert.duration_minutes else "",
            ]
            cell_range = f"A{idx}:F{idx}"
            ws.update(cell_range, [row_data], value_input_option="RAW")
            break

def delete_concert_in_sheet(concert_id: int):
    """
    해당 concert_id(=pk)와 같은 id를 가진 시트 행을 찾아 삭제(DELETE).
    """
    ws = get_worksheet("concerts")
    all_values = ws.get_all_values()

    for idx, row in enumerate(all_values[1:], start=2):  # 2행부터
        sheet_id = row[0]
        if sheet_id == str(concert_id):
            ws.delete_rows(idx)  # idx 행 삭제
            break

def create_review_in_sheet(review: Review):
    ws = get_worksheet("reviews")

    if not review.pk:
        review.save()

    row_data = [
        review.pk,
        review.concert_id,                 # 혹은 review.concert.pk
        review.nickname,
        str(review.date) if review.date else "",
        str(review.view_count),
        str(review.like_count),
        review.title,
        review.description or "",
        str(review.star_rating) if review.star_rating is not None else "",
    ]

    ws.append_row(row_data, value_input_option="RAW")

def read_all_reviews_from_sheet():
    ws = get_worksheet("reviews")
    all_values = ws.get_all_values()
    header = all_values[0]
    data_rows = all_values[1:]

    reviews_data = []
    for row in data_rows:
        if not row:
            continue
        row_dict = {}
        for i, col_name in enumerate(header):
            row_dict[col_name] = row[i] if i < len(row) else ""
        reviews_data.append(row_dict)

    return reviews_data

def update_review_in_sheet(review: Review):
    ws = get_worksheet("reviews")
    all_values = ws.get_all_values()

    for idx, row in enumerate(all_values[1:], start=2):
        sheet_id = row[0]
        if sheet_id == str(review.pk):
            row_data = [
                str(review.pk),
                str(review.concert.pk),
                review.nickname,
                str(review.date) if review.date else "",
                str(review.view_count),
                str(review.like_count),
                review.title,
                review.description or "",
                str(review.star_rating) if review.star_rating is not None else "",
            ]
            # A~I 열 업데이트
            cell_range = f"A{idx}:I{idx}"
            ws.update(cell_range, [row_data], value_input_option="RAW")
            break

def delete_review_in_sheet(review_id: int):
    ws = get_worksheet("reviews")
    all_values = ws.get_all_values()

    for idx, row in enumerate(all_values[1:], start=2):
        sheet_id = row[0]
        if sheet_id == str(review_id):
            ws.delete_rows(idx)
            break

from .models import Seat

def create_seat_in_sheet(seat: Seat):
    ws = get_worksheet("seats")

    if not seat.pk:
        seat.save()

    row_data = [
        seat.pk,
        seat.concert_id,  # seat.concert.pk
        str(seat.year),
        str(seat.month),
        str(seat.day_num),
        seat.day_str,
        seat.round_name,
        str(seat.round_time) if seat.round_time else "",
        seat.seat_class,
        str(seat.seat_count),
        seat.actors or "",
        str(seat.created_at) if seat.created_at else "",
    ]

    ws.append_row(row_data, value_input_option="RAW")

def read_all_seats_from_sheet():
    ws = get_worksheet("seats")
    all_values = ws.get_all_values()
    header = all_values[0]
    data_rows = all_values[1:]

    seats_data = []
    for row in data_rows:
        if not row:
            continue
        row_dict = {}
        for i, col_name in enumerate(header):
            row_dict[col_name] = row[i] if i < len(row) else ""
        seats_data.append(row_dict)

    return seats_data

def update_seat_in_sheet(seat: Seat):
    ws = get_worksheet("seats")
    all_values = ws.get_all_values()

    for idx, row in enumerate(all_values[1:], start=2):
        sheet_id = row[0]
        if sheet_id == str(seat.pk):
            row_data = [
                str(seat.pk),
                str(seat.concert.pk),
                str(seat.year),
                str(seat.month),
                str(seat.day_num),
                seat.day_str,
                seat.round_name,
                str(seat.round_time) if seat.round_time else "",
                seat.seat_class,
                str(seat.seat_count),
                seat.actors or "",
                str(seat.created_at) if seat.created_at else "",
            ]
            # A~L 열 업데이트
            cell_range = f"A{idx}:L{idx}"
            ws.update(cell_range, [row_data], value_input_option="RAW")
            break

def delete_seat_in_sheet(seat_id: int):
    ws = get_worksheet("seats")
    all_values = ws.get_all_values()

    for idx, row in enumerate(all_values[1:], start=2):
        sheet_id = row[0]
        if sheet_id == str(seat_id):
            ws.delete_rows(idx)
            break

def sync_all_concerts_to_sheet(request):
    """
    모든 Concert 객체를 구글 시트에 업sert(없으면 create, 있으면 update)하는 예시.
    """
    concerts = Concert.objects.all()
    for c in concerts:
        # 시트에서 해당 c.pk가 있는지 확인 후 있으면 update, 없으면 create
        # 간단히: 존재 여부 상관없이 delete -> create 하는 식으로 처리할 수도 있음
        update_concert_in_sheet(c)  # 없으면 그냥 무시되므로 create를 병행할 수도...

    return HttpResponse("Concert 동기화 완료")


def sync_all_concerts_from_sheet(request):
    """
    구글 시트 -> DB 로 Concert 데이터 전체 동기화 예시.
    """
    concerts_data = read_all_concerts_from_sheet()
    for row in concerts_data:
        # row는 예: {"id":"1","name":"테스트공연", ...}
        pk = row.get("id")
        if not pk:
            continue

        # DB Concert 갱신 또는 생성
        concert_obj, created = Concert.objects.update_or_create(
            pk=pk,
            defaults={
                "name": row.get("name"),
                "place": row.get("place"),
                "start_date": row.get("start_date") or None,
                "end_date": row.get("end_date") or None,
                "duration_minutes": row.get("duration_minutes") or None,
            }
        )
    return HttpResponse("Concert DB 업데이트 완료")

# sheets.py
def find_concert_in_sheet(name: str, place: str, start_date: str):
    """
    concerts 시트에서 name/place/start_date가 일치하는 행이 있는지 확인.
    있으면 해당 row(dict)를, 없으면 None 반환.
    """
    ws = get_worksheet("concerts")
    all_rows = ws.get_all_records()  # [{'id':'1','name':'AAA','place':'BBB', ...}, ...] 형태

    for row in all_rows:
        # 문자열 비교 주의 (start_date가 ''일 수 있으므로)
        # 여기서는 단순히 == 로 비교한다고 가정
        if (row.get("name") == name and
            row.get("place") == place and
            row.get("start_date") == (start_date or "")):
            return row
    return None


def create_concert_in_sheet_if_not_exists(concert: Concert):
    """
    시트에 동일 concert(name, place, start_date)가 없으면 새로 추가.
    """
    # DB pk가 없으면 먼저 DB에 저장
    if not concert.pk:
        concert.save()

    # 시트에서 검색
    existing_row = find_concert_in_sheet(
        name=concert.name,
        place=concert.place,
        start_date=str(concert.start_date) if concert.start_date else ""
    )
    if existing_row is not None:
        # 이미 시트에 존재하면 아무 것도 안 함
        return

    # 없으면 새 행 추가
    ws = get_worksheet("concerts")
    row_data = [
        concert.pk,
        concert.name,
        concert.place,
        str(concert.start_date) if concert.start_date else "",
        str(concert.end_date) if concert.end_date else "",
        str(concert.duration_minutes) if concert.duration_minutes else "",
    ]
    ws.append_row(row_data, value_input_option="RAW")


def sync_concert_sheet_to_db():
    """
    concerts 시트 전체를 읽어, DB에 없는 레코드만 저장.
    (id가 같거나, name/place/start_date 등이 같은지 확인 로직은 상황에 맞게 조정)
    """
    rows = read_all_concerts_from_sheet()  # [{'id':'1','name':'XXX',...}, ...]
    for row in rows:
        pk = row.get("id")
        if not pk:
            continue  # id가 비어있으면 스킵

        # DB에 pk=pk가 있는지 확인
        if Concert.objects.filter(pk=pk).exists():
            # 이미 같은 pk가 있으면 스킵 (혹은 update를 할 수도 있음)
            continue

        # 혹은 name/place/start_date로 중복 체크할 수도 있음
        # 아래는 단순 pk 기준으로만 확인:
        Concert.objects.create(
            pk=pk,
            name=row.get("name") or "",
            place=row.get("place") or "",
            start_date=row.get("start_date") or None,
            end_date=row.get("end_date") or None,
            duration_minutes=row.get("duration_minutes") or None
        )

def find_concert_row_by_id(pk_value: int):
    """
    concerts 시트에서 'id' 열이 pk_value인 행을 찾아
    - 찾으면 (row_index, row_data) 형태로 반환 (row_index는 2부터 시작)
    - 없으면 None 반환
    """
    ws = get_worksheet("concerts")
    all_values = ws.get_all_values()  # 2차원 리스트
    if not all_values:
        return None
    
    # 첫 행은 header: ["id", "name", "place", "start_date", "end_date", "duration_minutes"]
    for idx, row in enumerate(all_values[1:], start=2):  # 2행부터 데이터
        if len(row) > 0 and row[0] == str(pk_value):
            return (idx, row)
    return None


def create_or_update_concert_in_sheet(concert: Concert):
    """
    - 시트에서 concert.pk와 같은 'id' 열을 가진 행을 찾는다.
    - 있으면 해당 행을 update.
    - 없으면 append_row로 새로 추가.
    """
    ws = get_worksheet("concerts")

    if not concert.pk:
        concert.save()

    # pk 기준으로 시트에 같은 row 있는지 확인
    found = find_concert_row_by_id(concert.pk)
    row_data = [
        concert.pk,
        concert.name,
        concert.place,
        str(concert.start_date) if concert.start_date else "",
        str(concert.end_date) if concert.end_date else "",
        str(concert.duration_minutes) if concert.duration_minutes else "",
    ]

    if found is None:
        # 스프레드시트에 해당 pk 행이 없다면 새로 append
        ws.append_row(row_data, value_input_option="RAW")
        print(f"[스프레드시트] id={concert.pk} 새 행 추가")
    else:
        # 이미 같은 pk가 있으므로 update
        row_index, _old_row = found
        cell_range = f"A{row_index}:F{row_index}"  # 6열
        ws.update(cell_range, [row_data], value_input_option="RAW")
        print(f"[스프레드시트] id={concert.pk} 행 업데이트 (row={row_index})")
