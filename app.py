import os

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st


# ==========================================
# 1. ページ設定・基本設定
# ==========================================

st.set_page_config(
    page_title="就活エントリー管理",
    page_icon="💼",
    layout="wide"
)

# ログイン用ユーザー情報
USERS = {"sora": "112358"}

SPREADSHEET_NAME = "就活管理"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")


INDUSTRY_LIST = [
    "未設定",
    "IT・通信",
    "メーカー",
    "商社",
    "金融・保険",
    "コンサル・専門サービス",
    "広告・メディア",
    "不動産・建設",
    "小売・流通",
    "インフラ・交通",
    "公務・団体",
    "その他",
]

STATUS_LIST = [
    "検討中",
    "エントリー済",
    "一次面接",
    "二次面接",
    "最終面接",
    "内定",
    "お見送り",
]

# スプレッドシートの列構成
EXPECTED_COLS = [
    "企業名",
    "業界",
    "ログインID",
    "パスワード",
    "ステータス",
    "メモ",
    "URL",
    "志望動機",
]

# ログインロックの管理セル
LOCK_CELL = "L1"

# 連続ログイン失敗の上限
MAX_LOGIN_FAILURES = 5


# ==========================================
# 2. スプレッドシート接続
# ==========================================

@st.cache_resource
def get_sheet():

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    try:

        if "gcp_service_account" in st.secrets:

            creds_dict = dict(st.secrets["gcp_service_account"])

            creds = Credentials.from_service_account_info(
                creds_dict,
                scopes=scopes
            )

        elif os.path.exists(CREDENTIALS_FILE):

            creds = Credentials.from_service_account_file(
                CREDENTIALS_FILE,
                scopes=scopes
            )

        else:

            st.error(
                "認証情報が見つかりません。"
                "Streamlit Secrets または credentials.json を配置してください。"
            )

            st.stop()

        client = gspread.authorize(creds)

        spreadsheet = client.open(SPREADSHEET_NAME)

        return spreadsheet.sheet1

    except Exception as e:

        st.error(f"スプレッドシートへの接続に失敗しました: {e}")

        st.stop()


sheet = get_sheet()


# ==========================================
# 3. スプレッドシートのデータ読み込み
# ==========================================

def load_data_from_sheet():

    # A～H列だけを読み込む
    # K列・L列の管理情報は読み込まない
    data = sheet.get("A:H")

    # データがない、または見出し行しかない場合は空の表を返す
    if not data or len(data) < 2:

        return pd.DataFrame(columns=EXPECTED_COLS)

    # 1行目は見出しなので読み飛ばし、2行目以降を企業情報として使う
    rows = data[1:]

    # 列数を8列に統一
    normalized_rows = []

    for row in rows:

        row = list(row[:8])

        while len(row) < 8:
            row.append("")

        normalized_rows.append(row)

    # 【変更点】見出しの文字ではなく、列の「位置」で列名を決める
    # （H1の表記が少しずれていても志望動機が読めるようにするため）
    df = pd.DataFrame(
        normalized_rows,
        columns=EXPECTED_COLS
    )

    return df


# ==========================================
# 4. ログインロックの管理
# ==========================================

def is_locked():

    lock_status = sheet.acell(LOCK_CELL).value

    return str(lock_status).strip() == "1"


def lock_login():

    sheet.update_acell(LOCK_CELL, "1")


# ==========================================
# 5. セッション状態の初期化
# ==========================================

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "username" not in st.session_state:
    st.session_state["username"] = ""

if "login_failures" not in st.session_state:
    st.session_state["login_failures"] = 0

if "show_motivation_editor" not in st.session_state:
    st.session_state["show_motivation_editor"] = False


# ==========================================
# 6. ログイン画面
# ==========================================

if not st.session_state["logged_in"]:

    st.title("🔒 就活管理システム ログイン")

    # スプレッドシート上のロック状態を確認
    if is_locked():

        st.error(
            "🔒 ログインがロックされています。"
            "管理者にお問い合わせください。"
        )

        st.stop()

    with st.form("login_form"):

        username = st.text_input("ユーザーID")

        password = st.text_input(
            "パスワード",
            type="password"
        )

        submit = st.form_submit_button("ログイン")

        if submit:

            # 【変更点】送信された瞬間にもロック状態を再確認する
            # （ロック前から開いていた画面からのログインを防ぐため）
            if is_locked():

                st.error(
                    "🔒 ログインがロックされています。"
                    "管理者にお問い合わせください。"
                )

                st.stop()

            if username in USERS and USERS[username] == password:

                # ログイン成功
                st.session_state["logged_in"] = True

                st.session_state["username"] = username

                # 連続失敗回数をリセット
                st.session_state["login_failures"] = 0

                st.success("ログインに成功しました！")

                st.rerun()

            else:

                # ログイン失敗
                st.session_state["login_failures"] += 1

                failures = st.session_state["login_failures"]

                if failures >= MAX_LOGIN_FAILURES:

                    # 5回連続失敗でロック
                    lock_login()

                    st.error(
                        "ログインに5回連続で失敗したため、"
                        "アカウントをロックしました。"
                    )

                    st.rerun()

                else:

                    remaining = MAX_LOGIN_FAILURES - failures

                    st.error(
                        "ユーザーIDまたはパスワードが正しくありません。"
                    )

                    st.warning(
                        f"あと{remaining}回失敗するとログインがロックされます。"
                    )

    st.stop()


# ==========================================
# 7. メイン画面
# ==========================================

st.sidebar.write(
    f"👤 **ログイン中:** `{st.session_state['username']}`"
)

if st.sidebar.button("🚪 ログアウト"):

    st.session_state["logged_in"] = False

    st.session_state["username"] = ""

    st.session_state["login_failures"] = 0

    st.session_state["show_motivation_editor"] = False

    st.rerun()


st.title("💼 就活エントリー管理 Webアプリ")

df = load_data_from_sheet()
# --- 確認用（あとで消す） ---
st.sidebar.caption("版: 2026-11-23-debug")
with st.sidebar.expander("🔧 デバッグ情報"):
    st.write("列名:", list(df.columns))
    st.write("行数:", len(df))
    st.write("志望動機の列:", df["志望動機"].tolist())


# ==========================================
# 8. 企業情報の登録・編集・削除
# ==========================================

st.subheader("📝 データの登録 / 編集")

with st.expander("企業情報の追加・更新・削除", expanded=True):

    # 業界順に並べ替え
    df_sorted = df.copy()

    industry_order = {
        ind: idx
        for idx, ind in enumerate(INDUSTRY_LIST)
    }

    df_sorted["industry_rank"] = df_sorted["業界"].map(
        lambda x: industry_order.get(x, 999)
    )

    df_sorted = df_sorted.sort_values(
        by=["industry_rank", "企業名"]
    ).reset_index(drop=True)

    # 選択肢を作成
    options_map = {
        "【新規登録】": "【新規登録】"
    }

    for _, r in df_sorted.iterrows():

        label = (
            f"【{r['業界'] if r['業界'] else '未設定'}】 "
            f"{r['企業名']}"
        )

        options_map[label] = r["企業名"]

    selected_label = st.selectbox(
        "編集する企業を選択（業界別順）",
        list(options_map.keys()),
        key="selected_company_box"
    )

    selected_company = options_map[selected_label]

    # 選択企業の情報を取得
    if selected_company != "【新規登録】":

        row = df[df["企業名"] == selected_company].iloc[0]

        init_company = row["企業名"]

        init_industry = (
            row["業界"]
            if row["業界"] in INDUSTRY_LIST
            else "未設定"
        )

        init_my_id = row["ログインID"]

        init_password = row["パスワード"]

        init_status = (
            row["ステータス"]
            if row["ステータス"] in STATUS_LIST
            else "エントリー済"
        )

        init_memo = row["メモ"]

        init_url = row["URL"]

    else:

        init_company = ""
        init_industry = "未設定"
        init_my_id = ""
        init_password = ""
        init_status = "エントリー済"
        init_memo = ""
        init_url = ""

    # コピー用情報とマイページリンク
    if selected_company != "【新規登録】":

        st.markdown("**📋 コピー用情報 ＆ マイページリンク**")

        cp_col1, cp_col2, cp_col3 = st.columns([2, 2, 1.5])

        if init_my_id:

            cp_col1.caption("▼ ログインID")

            cp_col1.code(init_my_id, language=None)

        if init_password:

            cp_col2.caption("▼ パスワード")

            cp_col2.code(init_password, language=None)

        cp_col3.caption("▼ マイページ")

        if init_url and init_url.startswith("http"):

            cp_col3.link_button(
                "🌐 サイトを開く",
                init_url,
                use_container_width=True
            )

        elif init_url:

            cp_col3.link_button(
                "🌐 サイトを開く",
                f"https://{init_url}",
                use_container_width=True
            )

        else:

            cp_col3.info("URL未登録")

    # 企業情報入力フォーム
    with st.form("entry_form"):

        c1, c2 = st.columns(2)

        company = c1.text_input(
            "企業名*",
            value=init_company
        )

        industry = c2.selectbox(
            "業界・ジャンル",
            INDUSTRY_LIST,
            index=INDUSTRY_LIST.index(init_industry)
        )

        my_id = c1.text_input(
            "ログインID*",
            value=init_my_id
        )

        password = c2.text_input(
            "パスワード",
            value=init_password
        )

        status = c1.selectbox(
            "ステータス",
            STATUS_LIST,
            index=STATUS_LIST.index(init_status)
        )

        url = c2.text_input(
            "マイページURL",
            value=init_url
        )

        memo = st.text_input(
            "メモ",
            value=init_memo
        )

        btn_save = st.form_submit_button(
            "💾 保存（新規追加 / 上書き）"
        )

        if btn_save:

            if not company or not my_id:

                st.error("企業名とログインIDは必須項目です。")

            else:

                new_row = [
                    company,
                    industry,
                    my_id,
                    password,
                    status,
                    memo,
                    url,
                ]

                if (
                    selected_company != "【新規登録】"
                    and selected_company in df["企業名"].values
                ):

                    row_idx = (
                        df[df["企業名"] == selected_company].index[0] + 2
                    )

                    # A～G列だけ更新する
                    # H列の志望動機はそのまま残す
                    sheet.update(
                        f"A{row_idx}:G{row_idx}",
                        [new_row]
                    )

                    st.success(f"「{company}」を更新しました！")

                else:

                    # 新規登録時はH列も空欄で追加
                    new_row.append("")

                    sheet.append_row(new_row)

                    st.success(f"「{company}」を新規登録しました！")

                st.rerun()

    # 企業削除
    if selected_company != "【新規登録】":

        if st.button(
            "🗑️ 選択中の企業を削除",
            type="primary"
        ):

            row_idx = (
                df[df["企業名"] == selected_company].index[0] + 2
            )

            sheet.delete_rows(row_idx)

            st.success(f"「{selected_company}」を削除しました。")

            st.rerun()


# ==========================================
# 9. 志望動機の閲覧・編集
# ==========================================

st.divider()

st.subheader("📝 志望動機")

if st.button("志望動機を閲覧・編集する"):

    st.session_state["show_motivation_editor"] = True


if st.session_state["show_motivation_editor"]:

    if df.empty:

        st.info("登録されている企業がありません。")

    else:

        # 【変更点】企業名ではなく「表の行番号(index)」を選択肢にする
        # → 同名企業があっても、選んだ行にそのまま保存できる
        selected_idx = st.selectbox(
            "企業を選択",
            df.index.tolist(),
            format_func=lambda i: f"{df.loc[i, '企業名']}（{i + 2}行目）",
            key="motivation_company_select"
        )

        selected_motivation_company = df.loc[selected_idx, "企業名"]

        # スプレッドシート上の行番号（1行目は見出しなので +2）
        motivation_row_idx = selected_idx + 2

        current_motivation = df.loc[selected_idx, "志望動機"]

        with st.form("motivation_form"):

            # 【変更点】keyに行番号を入れて、企業を切り替えたら
            # テキストエリアの中身も確実に入れ替わるようにする
            motivation = st.text_area(
                "志望動機",
                value=current_motivation,
                height=300,
                placeholder="ここに志望動機を入力してください。",
                key=f"motivation_text_{selected_idx}"
            )

            save_motivation = st.form_submit_button(
                "💾 志望動機を保存"
            )

            if save_motivation:

                # 【変更点】value_input_option="RAW" で、「=」や「+」で
                # 始まる文章が数式として扱われるのを防ぐ
                sheet.update(
                    range_name=f"H{motivation_row_idx}",
                    values=[[motivation]],
                    value_input_option="RAW"
                )

                st.success(
                    f"「{selected_motivation_company}」の"
                    "志望動機を保存しました！"
                )

                st.rerun()

    if st.button("閉じる"):

        st.session_state["show_motivation_editor"] = False

        st.rerun()


# ==========================================
# 10. 登録企業一覧・絞り込み
# ==========================================

st.divider()

st.subheader("📊 登録企業一覧")

col_f1, col_f2 = st.columns([1, 2])

filter_ind = col_f1.selectbox(
    "🔍 業界で絞り込み",
    ["すべて"] + INDUSTRY_LIST
)

display_df = df.copy()

if filter_ind != "すべて":

    display_df = display_df[
        display_df["業界"] == filter_ind
    ]

display_df = display_df.sort_values(
    by="業界",
    ascending=True
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "URL": st.column_config.LinkColumn("マイページURL"),
        "志望動機": st.column_config.TextColumn("志望動機"),
    },
)
