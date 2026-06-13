#!/bin/bash
# キャッシュ削除 & 再起動スクリプト
# HTMLタグが文字として表示される・古い表示が残る場合に実行
echo "🧹 キャッシュを削除しています..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
find . -name "*.pyc" -delete 2>/dev/null; true
rm -rf ~/.streamlit/cache 2>/dev/null; true
echo "✅ 完了"
echo "🚀 起動します..."
streamlit run app.py
