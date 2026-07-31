from __future__ import annotations

import csv
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

import pandas as pd
import streamlit as st
from dateutil import parser as dtparser

from site_config import get_team_config

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MATCHES_PATH = DATA_DIR / "matches.csv"
NEWS_PATH = DATA_DIR / "ticket_news.csv"
METADATA_PATH = DATA_DIR / "metadata.json"
JST = timezone(timedelta(hours=9))
JP_WEEKDAYS = ("月", "火", "水", "木", "金", "土", "日")

TEAM = get_team_config()

MATCH_COLUMNS = (
    "match_key", "season", "competition_group", "competition_name",
    "round_name", "kickoff", "date_text", "sort_date", "side",
    "home", "away", "opponent", "stadium", "match_url",
    "socio_at", "membership_at", "general_at", "ticket_source_url",
    "ticket_source_name", "ticket_note", "last_checked",
)
NEWS_COLUMNS = ("published_at", "title", "url", "fetched_at")

st.set_page_config(
    page_title=TEAM["page_title"],
    page_icon=TEAM.get("page_icon", "🎟️"),
    layout="wide",
    initial_sidebar_state="collapsed",
)


def file_version(path: Path) -> tuple[int, int]:
    """キャッシュ更新判定に使う軽量なファイル署名。"""
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size
    except OSError:
        return 0, 0


@st.cache_data(show_spinner=False, ttl=300)
def read_csv_safe(
    path_text: str,
    columns: tuple[str, ...],
    version: tuple[int, int],
) -> tuple[dict[str, str], ...]:
    """CSVを標準ライブラリだけで読み込み、初期表示を軽量化する。"""
    del version  # キャッシュキーとしてのみ使用
    path = Path(path_text)
    if not path.exists() or path.stat().st_size == 0:
        return tuple()

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows: list[dict[str, str]] = []
            for source in reader:
                rows.append({column: (source.get(column) or "") for column in columns})
            return tuple(rows)
    except (OSError, csv.Error, UnicodeError):
        return tuple()


@st.cache_data(show_spinner=False, ttl=300)
def read_metadata(path_text: str, version: tuple[int, int]) -> dict:
    del version  # キャッシュキーとしてのみ使用
    path = Path(path_text)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}


def format_datetime(value: str, empty: str = "未発表") -> str:
    if not value or value in ("None", "nan", "NaT"):
        return empty
    try:
        dt = dtparser.isoparse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt.astimezone(JST).strftime("%Y/%m/%d %H:%M")
    except (TypeError, ValueError, OverflowError):
        return value


def parse_kickoff(value: str) -> datetime | None:
    """キックオフ日時をJSTへ正規化する。"""
    if not value:
        return None
    try:
        dt = dtparser.isoparse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt.astimezone(JST)
    except (TypeError, ValueError, OverflowError):
        return None


def format_match_date(kickoff: str, date_text: str) -> str:
    """スマホ表示用に、確定済みなら試合日とキックオフ時刻を返す。"""
    dt = parse_kickoff(kickoff)
    if dt is not None:
        return dt.strftime("%Y/%m/%d %H:%M")
    match = re.search(r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}", date_text or "")
    if match:
        return match.group(0).replace("-", "/")
    return date_text or "未定"


def build_desktop_date_markup(kickoff: str, date_text: str) -> tuple[str, str]:
    """PC表の試合日を、日付と時刻が見える2段表示にする。"""
    dt = parse_kickoff(kickoff)
    if dt is not None:
        date_label = f"{dt:%Y/%m/%d}({JP_WEEKDAYS[dt.weekday()]})"
        time_label = dt.strftime("%H:%M")
        full_label = f"{date_label} {time_label}"
        markup = (
            f'<span class="match-date-main">{html.escape(date_label)}</span>'
            f'<span class="match-time">{html.escape(time_label)}</span>'
        )
        return markup, full_label

    full_label = date_text or "未定"
    escaped = html.escape(full_label)
    # 候補日が複数ある場合は、列を広げなくても読めるよう改行する。
    escaped = escaped.replace(" or ", '<span class="date-or"> or </span><br>')
    return f'<span class="match-date-unfixed">{escaped}</span>', full_label


def safe_url(value: str) -> str:
    """表示用リンクはhttp/httpsだけ許可する。"""
    value = (value or "").strip()
    if value.startswith("https://") or value.startswith("http://"):
        return html.escape(value, quote=True)
    return ""


def is_upcoming_match(row: dict[str, str], today_jst) -> bool:
    for value in (row.get("kickoff", ""), row.get("sort_date", "")):
        if not value:
            continue
        try:
            dt = dtparser.isoparse(str(value))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            return dt.astimezone(JST).date() >= today_jst
        except (TypeError, ValueError, OverflowError):
            continue

    match = re.search(
        r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}",
        row.get("date_text", ""),
    )
    if match:
        try:
            return datetime.strptime(
                match.group(0).replace("/", "-"), "%Y-%m-%d"
            ).date() >= today_jst
        except ValueError:
            pass
    return True


def sort_matches(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            row.get("sort_date", "9999-12-31"),
            row.get("competition_group", ""),
        ),
    )


def build_mobile_match_cards(rows: list[dict[str, str]]) -> str:
    cards: list[str] = []
    for row in rows:
        side = row.get("side", "")
        side_label = "H" if side == "HOME" else "A"
        side_class = "home" if side == "HOME" else "away"
        match_date = format_match_date(
            row.get("kickoff", ""), row.get("date_text", "")
        )
        opponent = row.get("opponent", "") or (
            row.get("away", "") if side == "HOME" else row.get("home", "")
        )
        general_sale = format_datetime(row.get("general_at", ""))
        bold_class = (
            " mobile-sale-bold"
            if side == "AWAY" and general_sale != "未発表"
            else ""
        )
        calendar_url = safe_url(build_google_calendar_url(row))
        calendar_button = ""
        if calendar_url:
            calendar_button = (
                '<div class="mobile-calendar-row">'
                f'<a class="mobile-calendar-button" href="{calendar_url}" '
                'target="_blank" rel="noopener noreferrer">'
                'Googleカレンダーに追加</a>'
                '</div>'
            )

        cards.append(
            f'<article class="mobile-match-card {side_class}">'
            '<div class="mobile-match-top">'
            f'<span class="mobile-match-date">{html.escape(match_date)}</span>'
            f'<span class="mobile-side-badge {side_class}">{side_label}</span>'
            f'<span class="mobile-opponent">{html.escape(opponent or "未定")}</span>'
            '</div>'
            '<div class="mobile-sale-row">'
            '<span class="mobile-sale-label">一般発売</span>'
            f'<span class="mobile-sale-value{bold_class}">'
            f'{html.escape(general_sale)}</span>'
            '</div>'
            f'{calendar_button}'
            '</article>'
        )
    return '<div class="mobile-match-list">' + "".join(cards) + "</div>"


def format_desktop_match_date(kickoff: str, date_text: str) -> str:
    """PC表向けに、確定済みの試合日とキックオフ時刻を1セルへ表示する。"""
    dt = parse_kickoff(kickoff)
    if dt is not None:
        return f"{dt:%Y/%m/%d}({JP_WEEKDAYS[dt.weekday()]}) {dt:%H:%M}"
    return date_text or "未定"


def validated_link(value: str) -> str:
    """DataFrameのリンク列へ渡せるhttp/https URLだけを返す。"""
    value = (value or "").strip()
    if value.startswith("https://") or value.startswith("http://"):
        return value
    return ""


def parse_confirmed_sale_datetime(value: str) -> datetime | None:
    """日付と時刻が確定している一般発売日時だけをJSTで返す。"""
    value = (value or "").strip()
    if not value or value in ("None", "nan", "NaT", "未発表", "時刻未定"):
        return None

    # 日付だけの値を0:00として誤登録しないよう、時刻表記を必須にする。
    if not re.search(r"(?:T|\s)\d{1,2}:\d{2}", value):
        return None

    try:
        dt = dtparser.isoparse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt.astimezone(JST)
    except (TypeError, ValueError, OverflowError):
        return None


def build_google_calendar_url(row: dict[str, str]) -> str:
    """アウェイ一般発売日時をGoogleカレンダーへ1件追加するURLを作る。"""
    if row.get("side") != "AWAY":
        return ""

    start = parse_confirmed_sale_datetime(row.get("general_at", ""))
    if start is None:
        return ""
    end = start + timedelta(minutes=30)

    home = row.get("home", "") or "未定"
    away = row.get("away", "") or TEAM.get("team_name", "FC東京")
    matchup = f"{home} vs {away}"
    match_date = format_match_date(
        row.get("kickoff", ""), row.get("date_text", "")
    )
    stadium = row.get("stadium", "") or "未定"
    source_url = validated_link(
        row.get("ticket_source_url", "") or row.get("match_url", "")
    )

    details_lines = [
        f"{TEAM.get('team_name', 'FC東京')} アウェイゲーム チケット一般発売",
        "",
        f"試合日：{match_date}",
        f"対戦：{matchup}",
        f"会場：{stadium}",
    ]
    if source_url:
        details_lines.extend(["", "公式情報：", source_url])
    details_lines.extend(["", "※購入前に必ず公式情報をご確認ください。"])

    params = {
        "action": "TEMPLATE",
        "text": f"【チケット一般発売】{matchup}",
        # UTC表記にして、端末のタイムゾーン設定に左右されないようにする。
        "dates": (
            f"{start.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}/"
            f"{end.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"
        ),
        "details": "\n".join(details_lines),
        "location": stadium,
        "ctz": "Asia/Tokyo",
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def display_matches(
    rows: list[dict[str, str]],
    filter_mode: str,
    include_competition: bool,
    mobile_pc_mode: bool = False,
) -> None:
    if not rows:
        st.info("該当する試合はありません。")
        return

    # スマートフォンではカード表示、PCでは列幅を変更できる標準表を表示する。
    st.markdown(build_mobile_match_cards(rows), unsafe_allow_html=True)

    view_rows: list[dict[str, str]] = []
    sides: list[str] = []
    for row in rows:
        is_home = row.get("side") == "HOME"
        item: dict[str, str] = {
            "試合日": format_desktop_match_date(
                row.get("kickoff", ""), row.get("date_text", "")
            ),
            "区分": "ホーム" if is_home else "アウェイ",
            "節・ラウンド": row.get("round_name", "") or "—",
            "対戦カード": f'{row.get("home", "")} vs {row.get("away", "")}',
            "会場": row.get("stadium", "") or "未定",
        }
        if filter_mode != "アウェイ":
            item["SOCIO"] = (
                format_datetime(row.get("socio_at", "")) if is_home else "—"
            )
            item["OFFICIAL MEMBERSHIP"] = (
                format_datetime(row.get("membership_at", "")) if is_home else "—"
            )
        item["一般発売"] = format_datetime(row.get("general_at", ""))
        item["公式情報"] = validated_link(
            row.get("ticket_source_url", "") or row.get("match_url", "")
        )
        item["カレンダー"] = build_google_calendar_url(row)
        if include_competition:
            item = {"大会": row.get("competition_name", "") or "—", **item}
        view_rows.append(item)
        sides.append(row.get("side", ""))

    view = pd.DataFrame(view_rows)

    def row_style(series: pd.Series) -> list[str]:
        side = sides[series.name]
        background = home_color if side == "HOME" else away_color
        base = f"background-color:{background};color:#0f172a"
        styles = [base] * len(series)
        if side == "AWAY" and series.get("一般発売") != "未発表":
            general_index = view.columns.get_loc("一般発売")
            styles[general_index] = base + ";font-weight:800"
        return styles

    column_config: dict[str, object] = {
        "試合日": st.column_config.TextColumn("試合日", width=150),
        "区分": st.column_config.TextColumn("区分", width=70),
        "節・ラウンド": st.column_config.TextColumn("節・ラウンド", width=74),
        "対戦カード": st.column_config.TextColumn("対戦カード", width=190),
        "会場": st.column_config.TextColumn("会場", width=100),
        "一般発売": st.column_config.TextColumn("一般発売", width=128),
        "公式情報": st.column_config.LinkColumn(
            "公式情報", display_text="確認", width=72
        ),
        "カレンダー": st.column_config.LinkColumn(
            "カレンダー", display_text="追加", width=78
        ),
    }
    if "大会" in view.columns:
        # 初期表示はあえて狭くし、必要な場合はヘッダー境界をドラッグして広げる。
        column_config["大会"] = st.column_config.TextColumn("大会", width=62)
    if "SOCIO" in view.columns:
        column_config["SOCIO"] = st.column_config.TextColumn("SOCIO", width=126)
    if "OFFICIAL MEMBERSHIP" in view.columns:
        column_config["OFFICIAL MEMBERSHIP"] = st.column_config.TextColumn(
            "OFFICIAL MEMBERSHIP", width=136
        )

    st.markdown(
        '<div class="desktop-table-size-note">'
        '列見出しの境界を左右にドラッグすると、見出しと一覧の列幅が一緒に変わります。'
        '</div>',
        unsafe_allow_html=True,
    )

    # 表示行数に応じて高さを調整する。スマホのPC版表示では最低高さを広めに確保する。
    row_height = 36
    header_height = 46
    minimum_height = 420 if mobile_pc_mode else 250
    maximum_height = 700 if mobile_pc_mode else 620
    table_height = min(maximum_height, max(minimum_height, header_height + len(view) * row_height))
    st.dataframe(
        view.style.apply(row_style, axis=1),
        # スマホのPC版表示では列幅を縮めず、横スクロールで閲覧できるようにする。
        use_container_width=not mobile_pc_mode,
        hide_index=True,
        height=table_height,
        column_config=column_config,
    )


def build_news_list(rows: list[dict[str, str]]) -> str:
    items: list[str] = []
    for row in rows:
        url = safe_url(row.get("url", ""))
        title = html.escape(row.get("title", "") or "タイトルなし")
        published = html.escape(row.get("published_at", ""))
        if url:
            title_markup = (
                f'<a href="{url}" target="_blank" '
                f'rel="noopener noreferrer">{title}</a>'
            )
        else:
            title_markup = title
        items.append(
            '<li class="news-item">'
            f'<span>{published}</span>{title_markup}'
            '</li>'
        )
    return '<ul class="news-list">' + "".join(items) + "</ul>"


home_color = TEAM.get("home_row_color", "#eaf2ff")
away_color = TEAM.get("away_row_color", "#fdecec")

st.markdown(
    f"""
<style>
[data-testid="stSidebar"] {{display:none;}}
html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] .main {{overflow-x:hidden;}}
.block-container {{max-width:1320px; padding-top:2.3rem; padding-bottom:2rem;}}
.home-legend,.away-legend {{
  display:inline-block; padding:3px 10px; border-radius:5px;
  margin-right:8px; font-size:.85rem; border:1px solid rgba(15,23,42,.12);
  color:#0f172a !important;
}}
.home-legend {{background:{home_color};}}
.away-legend {{background:{away_color};}}
[data-testid="stDataFrame"] {{width:100% !important;}}
[data-testid="stDataFrameResizable"] {{width:100% !important;}}
.mobile-match-list {{display:none;}}
.mobile-match-card {{
  border:1px solid rgba(15,23,42,.12); border-radius:10px; padding:10px 11px;
  margin:0 0 8px; box-shadow:0 1px 3px rgba(0,0,0,.04);
  color:#0f172a !important;
}}
.mobile-match-card * {{color:#0f172a !important;}}
.mobile-match-card.home {{background:{home_color};}}
.mobile-match-card.away {{background:{away_color};}}
.mobile-match-top {{
  display:grid; grid-template-columns:auto auto minmax(0,1fr);
  align-items:center; gap:7px;
}}
.mobile-match-date {{font-weight:600; font-size:.84rem; white-space:nowrap;}}
.mobile-side-badge {{
  display:inline-flex; align-items:center; justify-content:center;
  width:24px; height:24px; border-radius:6px;
  font-size:.78rem; font-weight:800; color:#fff !important;
}}
.mobile-side-badge.home {{background:#2563eb;}}
.mobile-side-badge.away {{background:#dc2626;}}
.mobile-opponent {{font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}}
.mobile-sale-row {{
  display:flex; justify-content:space-between; align-items:center; gap:12px;
  border-top:1px solid rgba(15,23,42,.12); margin-top:8px; padding-top:7px;
}}
.mobile-sale-label {{font-size:.78rem; color:#475569 !important;}}
.mobile-sale-value {{font-size:.88rem;}}
.mobile-sale-bold {{font-weight:800;}}
.mobile-calendar-row {{margin-top:8px;}}
.mobile-calendar-button {{
  display:flex; align-items:center; justify-content:center; width:100%;
  box-sizing:border-box; padding:8px 10px; border-radius:7px;
  background:#2563eb; color:#fff !important; font-size:.84rem;
  font-weight:700; line-height:1.2; text-decoration:none !important;
}}
.mobile-calendar-button:hover {{background:#1d4ed8; color:#fff !important;}}
.desktop-table-size-note {{
  margin:.48rem 0 .3rem; font-size:.76rem; opacity:.72;
}}
/* PCでは切替は不要だが、表示しても機能上の影響はない。スマホでは補足を付ける。 */
#mobile-pc-view-enabled {{display:none;}}
.news-list {{list-style:none; padding:0; margin:.65rem 0 0;}}
.news-item {{
  display:grid; grid-template-columns:95px minmax(0,1fr); gap:10px;
  padding:9px 10px; border-bottom:1px solid rgba(127,127,127,.2);
}}
.news-item span {{font-size:.78rem; opacity:.72;}}
.news-item a {{font-weight:600; text-decoration:none;}}
.news-item a:hover {{text-decoration:underline;}}
@media (max-width:700px) {{
  html,body,[data-testid="stAppViewContainer"],[data-testid="stAppViewContainer"] .main {{
    width:100%; max-width:100%; overflow-x:hidden !important;
  }}
  .block-container {{
    width:100%; max-width:100%; box-sizing:border-box;
    padding-left:1rem; padding-right:1rem; padding-top:4.75rem;
    overflow-x:hidden !important;
  }}
  /* PC用DataFrameは本体だけでなく、Streamlitが確保した親要素ごと畳む。
     本体だけをdisplay:noneにすると、指定した表の高さがスマホ側に余白として残る。 */
  [data-testid="stElementContainer"]:has([data-testid="stDataFrame"]),
  [data-testid="stElementContainer"]:has([data-testid="stDataFrameResizable"]),
  .element-container:has([data-testid="stDataFrame"]),
  .element-container:has([data-testid="stDataFrameResizable"]),
  [data-testid="stElementContainer"]:has(.desktop-table-size-note),
  .element-container:has(.desktop-table-size-note),
  [data-testid="stDataFrame"],
  [data-testid="stDataFrameResizable"],
  .desktop-table-size-note {{
    display:none !important;
    width:0 !important;
    height:0 !important;
    min-height:0 !important;
    max-height:0 !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
  }}
  .mobile-match-list {{display:block;}}

  /* 切替ON時はスマホでもPC版DataFrameを表示し、カードを隠す。 */
  body:has(#mobile-pc-view-enabled) .mobile-match-list {{display:none !important;}}
  body:has(#mobile-pc-view-enabled) [data-testid="stElementContainer"]:has([data-testid="stDataFrame"]),
  body:has(#mobile-pc-view-enabled) [data-testid="stElementContainer"]:has([data-testid="stDataFrameResizable"]),
  body:has(#mobile-pc-view-enabled) .element-container:has([data-testid="stDataFrame"]),
  body:has(#mobile-pc-view-enabled) .element-container:has([data-testid="stDataFrameResizable"]) {{
    display:block !important;
    width:100% !important;
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:0 !important;
    padding:0 !important;
    overflow:visible !important;
  }}
  body:has(#mobile-pc-view-enabled) [data-testid="stElementContainer"]:has(.desktop-table-size-note),
  body:has(#mobile-pc-view-enabled) .element-container:has(.desktop-table-size-note),
  body:has(#mobile-pc-view-enabled) .desktop-table-size-note {{
    display:block !important;
    width:100% !important;
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:.48rem 0 .3rem !important;
    padding:0 !important;
    overflow:visible !important;
  }}
  /* DataFrame本体の高さはStreamlitのheight指定を維持する。
     height:autoで上書きすると、スマホで1行分だけになるため設定しない。 */
  body:has(#mobile-pc-view-enabled) [data-testid="stDataFrame"],
  body:has(#mobile-pc-view-enabled) [data-testid="stDataFrameResizable"] {{
    display:block !important;
    width:100% !important;
    min-height:420px !important;
    max-height:700px !important;
    margin:0 !important;
    padding:0 !important;
    overflow-x:auto !important;
  }}
  [data-testid="stHeadingWithActionElements"] h1 {{
    font-size:1.65rem !important; line-height:1.2 !important;
  }}
  .news-item {{grid-template-columns:1fr; gap:2px;}}
}}
</style>
""",
    unsafe_allow_html=True,
)

# Streamlit標準タイトルを使い、ライト／ダークのテーマ文字色へ確実に追従させる。
st.title(
    f"{TEAM.get('page_icon', '🎟️')} "
    f"{TEAM['service_name']}｜{TEAM['edition_name']}"
)

st.caption(f"{TEAM['subtitle']}｜{TEAM.get('season_label', '')}・非公式")

metadata = read_metadata(str(METADATA_PATH), file_version(METADATA_PATH))
last_updated = metadata.get("last_updated", "")
if last_updated:
    st.caption(f"最終更新：{format_datetime(last_updated, last_updated)}")
else:
    st.warning("データ更新待ちです。GitHub Actionsの「Run workflow」を実行してください。")

matches = list(
    read_csv_safe(str(MATCHES_PATH), MATCH_COLUMNS, file_version(MATCHES_PATH))
)
news = list(read_csv_safe(str(NEWS_PATH), NEWS_COLUMNS, file_version(NEWS_PATH)))
matches = sort_matches(matches)

if not matches:
    st.info("試合データはまだありません。初回データ更新後に表示されます。")
else:
    filter_mode = st.radio(
        "開催区分",
        ["すべて", "ホーム", "アウェイ"],
        horizontal=True,
        index=0,
    )
    hide_finished = st.checkbox(
        "終了済みの試合を非表示",
        value=True,
        help="試合日が今日より前の試合を一覧から除外します。",
    )

    if filter_mode == "ホーム":
        filtered = [row for row in matches if row.get("side") == "HOME"]
    elif filter_mode == "アウェイ":
        filtered = [row for row in matches if row.get("side") == "AWAY"]
    else:
        filtered = list(matches)

    if hide_finished:
        today_jst = datetime.now(JST).date()
        filtered = [row for row in filtered if is_upcoming_match(row, today_jst)]

    competition_options = [
        "すべて",
        "Ｊ１リーグ",
        "ルヴァンカップ",
        "天皇杯",
        "その他試合",
    ]
    competition_mode = st.radio(
        "大会",
        competition_options,
        horizontal=True,
        index=0,
    )
    competition_map = {
        "Ｊ１リーグ": "Ｊ１リーグ",
        "ルヴァンカップ": "ＪリーグＹＢＣルヴァンカップ",
        "天皇杯": "天皇杯",
        "その他試合": "その他試合",
    }
    if competition_mode != "すべて":
        target_group = competition_map[competition_mode]
        filtered = [
            row for row in filtered
            if row.get("competition_group") == target_group
        ]

    st.markdown(
        '<span class="home-legend">ホーム</span>'
        '<span class="away-legend">アウェイ</span>',
        unsafe_allow_html=True,
    )

    show_pc_table_on_mobile = st.toggle(
        "🖥️ PC版一覧を表示（横スクロール）",
        value=False,
        help="スマートフォンで、カード表示の代わりにPC版の一覧表を表示します。",
        key="show_pc_table_on_mobile",
    )
    if show_pc_table_on_mobile:
        st.markdown(
            '<div id="mobile-pc-view-enabled"></div>',
            unsafe_allow_html=True,
        )

    display_matches(
        filtered,
        filter_mode,
        include_competition=(competition_mode == "すべて"),
        mobile_pc_mode=show_pc_table_on_mobile,
    )

    if filter_mode == "アウェイ":
        st.caption("アウェイでは、ホームクラブ発表の一般発売日時だけを表示します。")
    else:
        st.caption(
            "ホームはSOCIO・OFFICIAL MEMBERSHIP・一般発売、"
            "アウェイは一般発売を表示します。"
        )
    st.caption(
        "Googleカレンダーへの追加は、アウェイ一般発売の日時が確定した試合だけ表示します。"
    )

st.divider()
st.subheader(f"{TEAM['team_name']} チケットニュース")
st.link_button(
    f"{TEAM['team_name']}公式 チケットニュース一覧を開く",
    TEAM["ticket_news_url"],
)

# 初期表示ではニュース一覧を組み立てない。必要な人だけ展開する。
show_news = st.checkbox("取得済みのチケットニュースを表示", value=True)
if show_news:
    if not news:
        st.caption(
            f"初回データ更新後、{TEAM['team_name']}公式チケットニュースへの"
            "リンクが表示されます。"
        )
    else:
        news = sorted(
            news,
            key=lambda row: row.get("published_at", ""),
            reverse=True,
        )[:20]
        st.markdown(build_news_list(news), unsafe_allow_html=True)

st.caption(
    "データは毎日7:00・19:00（日本時間）に自動更新します。"
    "GitHub Actionsの実行状況により遅れる場合があります。"
)
st.caption(TEAM["disclaimer"])
