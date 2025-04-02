import streamlit as st
from agents import Agent, Runner, WebSearchTool, handoff
from agents.tool import UserLocation
import datetime
import nest_asyncio
from dotenv import load_dotenv # .env ファイルを読み込むために追加

load_dotenv() # .env ファイルから環境変数を読み込む
nest_asyncio.apply() # イベントループのネストを許可

# --- セッション状態の初期化 ---
if 'result_text' not in st.session_state:
    st.session_state.result_text = ""
if 'target_school' not in st.session_state:
    st.session_state.target_school = ""
if 'year_option' not in st.session_state:
    st.session_state.year_option = '現在の情報に基づいて自動計算'
if 'manual_year' not in st.session_state:
    st.session_state.manual_year = datetime.date.today().year + 1
if 'is_running' not in st.session_state:
    st.session_state.is_running = False


# --- Streamlit UI ---
st.title("学校入試情報調査アプリ")

# 学校名の入力 (セッション状態を使用)
st.session_state.target_school = st.text_input(
    "調査対象の学校名や条件を入力してください:",
    value=st.session_state.target_school,
    disabled=st.session_state.is_running # 調査中は無効化
)

# 年度を自動計算するか、手動で入力するか選択 (セッション状態を使用)
st.session_state.year_option = st.radio(
    "年度の指定方法を選択してください:",
    ('現在の情報に基づいて自動計算', '手動で年度を指定'),
    index=0 if st.session_state.year_option == '現在の情報に基づいて自動計算' else 1,
    disabled=st.session_state.is_running # 調査中は無効化
)

target_year_str = ""
if st.session_state.year_option == '現在の情報に基づいて自動計算':
    # 現在の日付に基づいて年度を自動設定
    today = datetime.date.today()
    current_year = today.year
    # 4月1日以降は翌年の西暦年、3月31日以前は現在の西暦年を年度とする
    if today.month >= 4:
        academic_year = current_year + 1 # 翌年の年度
    else:
        academic_year = current_year # 現在の年の年度
    target_year_str = f"{academic_year}年度"
    st.write(f"自動計算された調査年度: {target_year_str}")
else:
    # 手動で年度を入力 (セッション状態を使用)
    st.session_state.manual_year = st.number_input(
        "調査対象の年度（西暦）を入力してください:",
        min_value=2000,
        max_value=2100,
        value=st.session_state.manual_year,
        step=1,
        disabled=st.session_state.is_running # 調査中は無効化
    )
    if st.session_state.manual_year:
        target_year_str = f"{st.session_state.manual_year}年度"
    st.write(f"指定された調査年度: {target_year_str}")

# ボタン用の列を作成
col1, col2 = st.columns(2)

# 調査開始ボタン
with col1:
    if st.button("調査開始", disabled=st.session_state.is_running): # 調査中は無効化
        if not st.session_state.target_school:
            st.warning("学校名を入力してください。")
        elif not target_year_str:
            st.warning("年度を指定してください。")
        else:
            st.info(f"{st.session_state.target_school} の {target_year_str} の入試情報を調査します...")
            st.session_state.result_text = "" # 結果をリセット
            st.session_state.is_running = True # 調査開始フラグを立てる

            # --- エージェント実行ロジック ---
            try:
                # Web検索ツールの設定
                web_search_tool = WebSearchTool(
                user_location=UserLocation(
                    type="approximate",
                    country="JP",
                    timezone="Asia/Tokyo"
                )
            )

                # --- エージェント定義 ---

                # 0. 学校存在チェッカー (新規追加)
                SchoolExistenceChecker = Agent(
                    name="SchoolExistenceChecker",
                    instructions=f"あなたは「{st.session_state.target_school}」という学校が実在するかどうかを Web 検索で確認する専門家です。学校の公式サイトや信頼できる情報源（例: Wikipedia、教育関連ポータルサイト）を探してください。存在する場合は学校名をそのまま返し、存在しない、または確認できない場合は 'SCHOOL_NOT_FOUND' という文字列だけを返してください。",
                    tools=[web_search_tool]
                )

                # 1. 公式情報リサーチャー
                OfficialInfoResearcher = Agent(
                    name="OfficialInfoResearcher",
                    instructions=f"あなたは {st.session_state.target_school} の公式ウェブサイトや信頼できる教育情報サイトから、{target_year_str} の（現時点で利用可能な最新の）入試要綱、科目、日程に関する公式情報を正確に収集する専門家です。特に指定がない限り、最新の確定情報を優先してください。",
                    tools=[web_search_tool]
                )
                # DetailedExamInfoResearcher エージェントの定義を追加
                DetailedExamInfoResearcher = Agent(
                    name="DetailedExamInfoResearcher",
                    instructions=f"あなたは `OfficialInfoResearcher` が特定した {st.session_state.target_school} の {target_year_str} の各入試（種類と日程）について、さらに詳細な情報を深掘りする専門家です。具体的には、各入試のテスト科目、試験時間、配点、出題範囲などの詳細情報を公式ウェブサイトや信頼できる情報源から収集してください。",
                    tools=[web_search_tool]
                )
                # TranscriptScoreResearcher エージェントの定義を追加
                TranscriptScoreResearcher = Agent(
                    name="TranscriptScoreResearcher",
                    instructions=f"あなたは {st.session_state.target_school} の {target_year_str} の入試において、内申点（調査書点）が必要かどうか、また必要な場合はどのように評価されるか（例: 点数化の方法、学科試験との比率、重視される学年や科目など）を調査する専門家です。公式の入試要綱や信頼できる情報源から正確な情報を収集してください。",
                    tools=[web_search_tool]
                )
                # DeviationScoreResearcher エージェントの定義を追加
                DeviationScoreResearcher = Agent(
                    name="DeviationScoreResearcher",
                    instructions=f"あなたは {st.session_state.target_school} の偏差値を調査する専門家です。信頼できる情報源（例: 大手予備校のウェブサイト、高校受験情報ポータルサイトなど）を複数参照し、最新の偏差値情報を収集してください。情報源によって偏差値が異なる場合は、その旨も報告してください。",
                    tools=[web_search_tool]
                )
                FutureTrendsResearcher = Agent(
                    name="FutureTrendsResearcher",
                    instructions=f"あなたは教育関連ニュース、学校の発表、過去の変更履歴などを調査し、{target_year_str}の{st.session_state.target_school}の入試に関する予測や可能性のある変更点について情報を収集する専門家です。情報は未確定である可能性を明記してください。",
                    tools=[web_search_tool]
                )
                FactCheckerAgent = Agent(
                    name="FactCheckerAgent",
                    instructions="あなたはリサーチエージェントから提供された情報を検証するファクトチェッカーです。情報の正確性、出典の信頼性、URLの有効性を確認し、矛盾点や未確定な情報があれば指摘してください。",
                )
                WriterAgent = Agent(
                    name="WriterAgent",
                    instructions="あなたは検証済みの受験情報に基づいて、受験生向けの明確で分かりやすいレポートを作成するライターです。収集された情報、参照URL、および情報の確度（特に未来の情報に関する注意点）を正確に伝えてください。"
                )
                CoordinatorAgent = Agent(
                    name="CoordinatorAgent",
                    instructions=f"""あなたは高校受験情報調査のコーディネーターです。以下の手順で進めてください。
1. まず、`SchoolExistenceChecker` に学校名「{st.session_state.target_school}」の存在確認を依頼します。
2. `SchoolExistenceChecker` から 'SCHOOL_NOT_FOUND' という応答があった場合は、他のリサーチは一切行わず、最終的な出力として「入力された学校の情報が見つかりませんでした。」というメッセージだけを生成してください。
3. 学校が存在する場合（'SCHOOL_NOT_FOUND' 以外の応答があった場合）のみ、以下のステップに進みます。
    a. ユーザーのリクエスト「{st.session_state.target_school}の{target_year_str}の入試の要綱、それぞれの入試の実施日時、テストの詳細、内申点の要否・評価方法、および偏差値を調べてください。」を分析します。
    b. 必要な情報を特定し、以下のリサーチャーにタスクを割り当てます:
        - `OfficialInfoResearcher`: 基本的な入試要綱、種類、日程の調査。
        - `DetailedExamInfoResearcher`: 各入試のテスト科目、時間、配点などの詳細情報の調査。
        - `TranscriptScoreResearcher`: 内申点の要否、評価方法、影響度などの調査。
        - `DeviationScoreResearcher`: 学校の偏差値の調査。
        - `FutureTrendsResearcher`: {target_year_str} の入試に関する予測や変更点の調査。
    c. すべてのリサーチャーから得られた結果を `FactCheckerAgent` に渡し、検証させます。
    d. 検証済みの情報を `WriterAgent` に渡し、収集されたすべての情報（基本情報、詳細情報、内申点情報、偏差値情報、将来の動向）を含む最終的なレポート作成を指示します。""",
                    handoffs=[SchoolExistenceChecker, OfficialInfoResearcher, DetailedExamInfoResearcher, TranscriptScoreResearcher, DeviationScoreResearcher, FutureTrendsResearcher, FactCheckerAgent, WriterAgent] # DeviationScoreResearcher を追加
                )

                # --- 実行 ---
                # initial_prompt も更新
                initial_prompt = f"{st.session_state.target_school}の{target_year_str}の入試の要綱、それぞれの入試の実施日時、テストの詳細（科目、時間、配点など）、内申点の要否・評価方法、および偏差値を調べてください。"

                with st.spinner('エージェントが情報を調査中です...'):
                    result = Runner.run_sync(
                        CoordinatorAgent,
                        initial_prompt,
                    )

                # 最終結果をセッション状態に保存
                if result and result.final_output:
                    st.session_state.result_text = result.final_output
                else:
                    st.session_state.result_text = "エラー: 調査結果を取得できませんでした。"
                    st.error(st.session_state.result_text)

            except Exception as e:
                st.session_state.result_text = f"エラーが発生しました: {e}"
                st.error(st.session_state.result_text)
            finally:
                st.session_state.is_running = False # 調査完了またはエラー時にフラグを下ろす
                st.rerun() # UIを更新して入力を再度有効化

# リセットボタン
with col2:
    if st.button("リセット"):
        st.session_state.target_school = ""
        st.session_state.year_option = '現在の情報に基づいて自動計算'
        st.session_state.manual_year = datetime.date.today().year + 1
        st.session_state.result_text = ""
        st.session_state.is_running = False # 実行フラグもリセット
        st.rerun() # 画面を再描画して入力をクリア


# 最終結果の出力 (セッション状態から)
if st.session_state.result_text:
    st.subheader("調査結果")
    # 結果をテキストエリアに表示（コピー用）
    st.text_area("結果内容（コピー用）:", st.session_state.result_text, height=150)
    # 結果をMarkdown形式で表示（リンクなどを有効にするため）
    st.markdown("---") # 区切り線
    st.markdown("**表示結果:**")
    st.markdown(st.session_state.result_text) # unsafe_allow_html=True は必要に応じて追加
    # if "エラー" in st.session_state.result_text: # エラー表示は try-except 内で行うため不要
    #     st.error(st.session_state.result_text)
    # else:
    #     st.markdown(st.session_state.result_text) # Markdown形式で表示
# else ブロックと重複コードを削除 (エラーは try-except でハンドルされ result_text に入る)

# アプリの実行方法についての説明
st.sidebar.info("""
**使い方:**
1. 調査したい学校名を入力します。
2. 調査対象の年度を指定します（自動計算または手動入力）。
3. 「調査開始」ボタンをクリックします。
4. エージェントが情報を収集し、結果が表示されるまで待ちます。

**実行方法:**
ターミナルで以下のコマンドを実行してください:
```bash
streamlit run streamlit_app.py
```
""")
