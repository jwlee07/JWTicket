import gspread
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials

from .models import Concert, Review, Seat

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
    spreadsheet = client.open_by_key(settings.GOOGLE_SHEET_KEY)
    print(f"[구글 스프레드시트] {spreadsheet.title} 열기")
    return spreadsheet

def get_worksheet(sheet_name):
    """
    sheet_name(예: concerts, reviews, seats)에 해당하는 worksheet를 반환
    """
    ss = open_ts_ticket_sheet()
    print(f"[구글 스프레드시트] {sheet_name} 시트 열기")
    return ss.worksheet(sheet_name)

# ------------------------------------------------------------------------------
# Concert 
# ------------------------------------------------------------------------------

def read_all_concerts_from_sheet():
    """
    concerts 시트에서 모든 행을 읽어 파이썬 dict 리스트로 반환.
    """
    ws = get_worksheet("concerts")
    all_values = ws.get_all_values()
    if not all_values:
        print("[concerts 시트] 데이터 없음")
        return []

    header = all_values[0]
    data_rows = all_values[1:]

    concerts_data = []
    for row in data_rows:
        if not row:
            continue
        row_dict = {}
        for i, col_name in enumerate(header):
            row_dict[col_name] = row[i] if i < len(row) else ""
        concerts_data.append(row_dict)

    print(f"[concerts 시트] {len(concerts_data)}개 행 읽음")
    return concerts_data

def find_concert_row_by_id(pk_value: int):
    """
    concerts 시트에서 'id' 열이 pk_value인 행을 찾아
    - 찾으면 (row_index, row_data) 형태로 반환
    - 없으면 None
    """
    ws = get_worksheet("concerts")
    all_values = ws.get_all_values()
    if not all_values:
        print(f"[concerts 시트] 데이터 없음")
        return None

    for idx, row in enumerate(all_values[1:], start=2):
        if row and row[0] == str(pk_value):
            return (idx, row)
    return None

def create_or_update_concert_in_sheet(concert: Concert):
    """
    1) 시트에서 concert.pk와 같은 id가 있는지 찾는다
    2) 있으면 update, 없으면 append
    """
    ws = get_worksheet("concerts")

    if not concert.pk:
        concert.save()
        print(f"[DB] Concert pk 없어서 새로 저장: {concert.pk}")

    found = find_concert_row_by_id(concert.pk)
    row_data = [
        str(concert.pk),
        concert.name or "",
        concert.place or "",
        str(concert.start_date) if concert.start_date else "",
        str(concert.end_date) if concert.end_date else "",
        str(concert.duration_minutes) if concert.duration_minutes else "",
        str(concert.genre) if concert.genre else "",
    ]
    print(f"[concerts 시트] id={concert.pk} 찾기 결과: {found}")

    if found is None:
        # 시트에 pk가 없으므로 append
        ws.append_row(row_data, value_input_option="RAW")
        print(f"[concerts 시트] id={concert.pk} 새 행 추가")
    else:
        # 이미 있으면 update
        row_index, _old_row = found
        cell_range = f"A{row_index}:F{row_index}"
        ws.update(cell_range, [row_data], value_input_option="RAW")
        print(f"[concerts 시트] id={concert.pk} 행 업데이트 (row={row_index})")

def sync_concert_sheet_to_db():
    """
    concerts 시트를 다시 읽어, DB에 없는 pk만 새로 저장
    """
    rows = read_all_concerts_from_sheet()
    for row in rows:
        pk = row.get("id")
        if not pk:
            print(f"[concerts 시트] id 없음")
            continue
        if Concert.objects.filter(pk=pk).exists():
            print(f"[DB] Concert pk={pk} 이미 있음")
            continue

        Concert.objects.create(
            pk=pk,
            name=row.get("name") or "",
            place=row.get("place") or "",
            start_date=row.get("start_date") or None,
            end_date=row.get("end_date") or None,
            duration_minutes=row.get("duration_minutes") or None,
            genre=row.get("genre") or None,
        )
        print(f"[DB] Concert pk={pk} 새로 저장")

def sync_db_concerts_to_sheet():
    """
    DB의 Concert 전부 조회 후, 시트에 없는 pk만 batch로 추가
    """
    concerts = Concert.objects.all()
    ws = get_worksheet("concerts")

    # 시트에서 이미 존재하는 id 추출
    all_rows = ws.get_all_records()
    existing_ids = set(str(r.get("id")) for r in all_rows if r.get("id"))

    batch_data = []
    for concert in concerts:
        if str(concert.pk) not in existing_ids:
            row_data = [
                str(concert.pk),
                concert.name or "",
                concert.place or "",
                str(concert.start_date) if concert.start_date else "",
                str(concert.end_date) if concert.end_date else "",
                str(concert.duration_minutes) if concert.duration_minutes else "",
                str(concert.genre) if concert.genre else "",
            ]
            batch_data.append(row_data)

    if batch_data:
        ws.append_rows(batch_data, value_input_option="RAW")
        print(f"[Concert] {len(batch_data)}개 레코드를 시트에 일괄 추가 완료")
    else:
        print("[Concert] 시트에 추가할 항목이 없습니다.")


# ------------------------------------------------------------------------------
# Review 관련 로직
# ------------------------------------------------------------------------------

def read_all_reviews_from_sheet():
    """
    reviews 시트에서 모든 행을 읽어 파이썬 dict 리스트로 반환.
    """
    ws = get_worksheet("reviews")
    all_values = ws.get_all_values()

    if not all_values:
        print(f"[reviews 시트] 데이터 없음")
        return []

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

    print(f"[reviews 시트] {len(reviews_data)}개 행 읽음")
    return reviews_data

def find_review_row_by_id(pk_value: int):
    """
    reviews 시트에서 'id' 열이 pk_value인 행 찾기
    """
    ws = get_worksheet("reviews")
    all_values = ws.get_all_values()

    if not all_values:
        print(f"[reviews 시트] 데이터 없음")
        return None

    for idx, row in enumerate(all_values[1:], start=2):
        if row and row[0] == str(pk_value):
            return (idx, row)
    return None

def create_or_update_review_in_sheet(review: Review):
    """
    1) reviews 시트에 pk가 있는지 확인
    2) 있으면 update, 없으면 append
    """
    ws = get_worksheet("reviews")

    if not review.pk:
        review.save()
        print(f"[DB] Review pk 없어서 새로 저장: {review.pk}")

    found = find_review_row_by_id(review.pk)
    row_data = [
        str(review.pk),
        str(review.concert_id),  # or review.concert.pk
        review.nickname or "",
        str(review.date) if review.date else "",
        str(review.view_count),
        str(review.like_count),
        review.title or "",
        review.description or "",
        str(review.star_rating) if review.star_rating is not None else "",
        review.emotion or "",
    ]

    if found is None:
        ws.append_row(row_data, value_input_option="RAW")
        print(f"[reviews 시트] id={review.pk} 새 행 추가")
    else:
        row_index, _old_row = found
        cell_range = f"A{row_index}:I{row_index}"
        ws.update(cell_range, [row_data], value_input_option="RAW")
        print(f"[reviews 시트] id={review.pk} 행 업데이트 (row={row_index})")

def sync_reviews_sheet_to_db():
    """
    reviews 시트 전체 읽어, DB에 없는 pk만 create
    """
    rows = read_all_reviews_from_sheet()
    for row in rows:
        pk = row.get("id")
        if not pk:
            print(f"[reviews 시트] id 없음")
            continue
        if Review.objects.filter(pk=pk).exists():
            print(f"[DB] Review pk={pk} 이미 있음")
            continue

        Review.objects.create(
            pk=pk,
            concert_id=row.get("concert_id") or None,
            nickname=row.get("nickname") or "",
            date=row.get("date") or None,
            view_count=row.get("view_count") or 0,
            like_count=row.get("like_count") or 0,
            title=row.get("title") or "",
            description=row.get("description") or "",
            star_rating=row.get("star_rating") or None,
        )
        print(f"[DB] Review pk={pk} 새로 저장")

def sync_db_reviews_to_sheet():
    """
    DB의 Review 전부 조회 후,
    스프레드시트 reviews 시트에 pk가 없으면 batch로 추가
    """
    reviews = Review.objects.all()
    ws = get_worksheet("reviews")

    all_rows = ws.get_all_records()
    existing_ids = set(str(r.get("id")) for r in all_rows if r.get("id"))

    batch_data = []
    for r in reviews:
        if str(r.pk) not in existing_ids:
            row_data = [
                str(r.pk),
                str(r.concert_id),
                r.nickname or "",
                str(r.date) if r.date else "",
                str(r.view_count),
                str(r.like_count),
                r.title or "",
                r.description or "",
                str(r.star_rating) if r.star_rating is not None else "",
                r.emotion or "",
            ]
            batch_data.append(row_data)

    if batch_data:
        ws.append_rows(batch_data, value_input_option="RAW")
        print(f"[Review] {len(batch_data)}개 레코드를 시트에 일괄 추가 완료")
    else:
        print("[Review] 시트에 추가할 항목 없음")

# ------------------------------------------------------------------------------
# Seat 관련 로직
# ------------------------------------------------------------------------------

def read_all_seats_from_sheet():
    """
    seats 시트에서 모든 행을 읽어 파이썬 dict 리스트로 반환.
    """
    ws = get_worksheet("seats")
    all_values = ws.get_all_values()

    if not all_values:
        print(f"[seats 시트] 데이터 없음")
        return []

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

    print(f"[seats 시트] {len(seats_data)}개 행 읽음")
    return seats_data

def find_seat_row_by_id(pk_value: int):
    """
    seats 시트에서 'id' 열이 pk_value인 행을 찾아
    - 찾으면 (row_index, row_data) 반환
    - 없으면 None
    """
    ws = get_worksheet("seats")
    all_values = ws.get_all_values()

    if not all_values:
        print(f"[seats 시트] 데이터 없음")
        return None

    for idx, row in enumerate(all_values[1:], start=2):
        if row and row[0] == str(pk_value):
            return (idx, row)
    return None

def create_or_update_seat_in_sheet(seat: Seat):
    """
    1) seats 시트에 pk가 있는지 확인
    2) 있으면 update, 없으면 append
    """
    ws = get_worksheet("seats")

    if not seat.pk:
        seat.save()
        print(f"[DB] Seat pk 없어서 새로 저장: {seat.pk}")

    found = find_seat_row_by_id(seat.pk)
    row_data = [
        str(seat.pk),
        str(seat.concert_id),
        str(seat.year),
        str(seat.month),
        str(seat.day_num),
        seat.day_str or "",
        seat.round_name or "",
        str(seat.round_time) if seat.round_time else "",
        seat.seat_class or "",
        str(seat.seat_count),
        seat.actors or "",
        str(seat.created_at) if seat.created_at else "",
    ]

    if found is None:
        ws.append_row(row_data, value_input_option="RAW")
        print(f"[seats 시트] id={seat.pk} 새 행 추가")
    else:
        row_index, _old_row = found
        cell_range = f"A{row_index}:L{row_index}"
        ws.update(cell_range, [row_data], value_input_option="RAW")
        print(f"[seats 시트] id={seat.pk} 행 업데이트 (row={row_index})")

def sync_seats_sheet_to_db():
    """
    seats 시트 전체 읽어, DB에 없는 pk만 create
    """
    rows = read_all_seats_from_sheet()
    for row in rows:
        pk = row.get("id")
        if not pk:
            continue
        if Seat.objects.filter(pk=pk).exists():
            continue

        Seat.objects.create(
            pk=pk,
            concert_id=row.get("concert_id") or None,
            year=row.get("year") or 0,
            month=row.get("month") or 0,
            day_num=row.get("day_num") or 0,
            day_str=row.get("day_str") or "",
            round_name=row.get("round_name") or "",
            round_time=row.get("round_time") or None,
            seat_class=row.get("seat_class") or "",
            seat_count=row.get("seat_count") or 0,
            actors=row.get("actors") or "",
            created_at=row.get("created_at") or None,
        )
        print(f"[DB] Seat pk={pk} 새로 저장")

def sync_db_seats_to_sheet():
    """
    DB의 Seat 전부 조회 후, 시트에 없는 pk만 batch로 추가
    """
    seats = Seat.objects.all()
    ws = get_worksheet("seats")

    all_rows = ws.get_all_records()
    existing_ids = set(str(r.get("id")) for r in all_rows if r.get("id"))

    batch_data = []
    for st in seats:
        if str(st.pk) not in existing_ids:
            row_data = [
                str(st.pk),
                str(st.concert_id),
                str(st.year),
                str(st.month),
                str(st.day_num),
                st.day_str or "",
                st.round_name or "",
                str(st.round_time) if st.round_time else "",
                st.seat_class or "",
                str(st.seat_count),
                st.actors or "",
                str(st.created_at) if st.created_at else "",
            ]
            batch_data.append(row_data)

    if batch_data:
        ws.append_rows(batch_data, value_input_option="RAW")
        print(f"[Seat] {len(batch_data)}개 레코드를 시트에 일괄 추가 완료")
    else:
        print("[Seat] 시트에 추가할 항목이 없습니다.")

def sync_patterns_to_sheet(pattern_data):
    """
    patterns 시트에서 nickname 행을 찾아,
      * 없으면 -> 배치 append
      * 있으면 -> view_count 비교(새로운 게 더 크면 배치 update, 작거나 같으면 skip)
    한 번의 update( batch_update )와 한 번의 append( append_rows )로 처리
    """

    ws = get_worksheet("patterns")

    # 시트 전체 읽기
    all_values = ws.get_all_values()
    if not all_values:
        print("[patterns 시트] 데이터 없음(헤더도 없음)")
        return
    print(f"[patterns 시트] {len(all_values)}개 행 읽음")
    
    header = all_values[0]
    data_rows = all_values[1:]
    print(f"[patterns] {len(pattern_data)}개 닉네임 패턴 데이터")

    # nickname -> (row_index, old_view_count) 매핑
    nickname_dict = {}
    for idx, row in enumerate(data_rows, start=2):
        if not row or len(row) < 3:
            continue
        old_nickname = row[0]
        try:
            old_view_count = int(row[2])
        except ValueError:
            old_view_count = 0

        nickname_dict[old_nickname] = {
            "row_index": idx,
            "view_count": old_view_count
        }
    print(f"[patterns] {len(nickname_dict)}개 닉네임 행 읽음")

    # 업데이트할 행들 (이미 닉네임이 존재 & new_view_count > old_view_count)
    update_requests = []
    # 새로 append할 행들 (nickname이 시트에 없음)
    append_data = []

    for nickname, concerts in pattern_data.items():
        new_view_count = len(concerts)
        patterns_list = [f"{c['concert']}({c['date']})" for c in concerts]
        new_view_patterns = " → ".join(patterns_list)

        if nickname in nickname_dict:
            # 이미 시트에 있음 -> view_count 비교
            old_info = nickname_dict[nickname]
            old_count = old_info["view_count"]
            row_index = old_info["row_index"]

            if new_view_count > old_count:
                # 더 클 때만 update
                row_data = [
                    nickname,
                    new_view_patterns,
                    str(new_view_count)
                ]
                range_str = f"A{row_index}:C{row_index}"  # nickname, view_patterns, view_count

                # batch_update용 요청 형식
                update_requests.append({
                    "range": range_str,
                    "values": [row_data]
                })
            else:
                # 작거나 같으면 skip
                print(f"[patterns] nickname={nickname} (old={old_count} >= new={new_view_count}), skip")

        else:
            # nickname이 시트에 없음 -> append
            row_data = [
                nickname,
                new_view_patterns,
                str(new_view_count)
            ]
            append_data.append(row_data)
    print(f"[patterns] update_requests={len(update_requests)}, append_data={len(append_data)}")

    # 수정할 행들
    if update_requests:
        sh = ws.spreadsheet
        body = {
            "valueInputOption": "RAW",
            "data": update_requests
        }
        sh.values_batch_update(body)
        print(f"[patterns] {len(update_requests)}개 닉네임 행 values_batch_update 완료")
    else:
        print("[patterns] update 대상 없음")

    # 새 닉네임
    if append_data:
        ws.append_rows(append_data, value_input_option="RAW")
        print(f"[patterns] {len(append_data)}개 닉네임 append_rows 완료")
    else:
        print("[patterns] append 대상 없음")