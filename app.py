from __future__ import annotations

import streamlit as st
from rag.ask import ask

st.set_page_config(page_title="Pokemon RAG Analyzer", page_icon="⚔️", layout="centered")

st.title("⚔️ Pokemon RAG Analyzer")
st.caption("Ask team-building, stats, or matchup questions.")

question = st.text_input("Your question", placeholder="Who has the highest speed?")
top_k = st.slider("Top-K retrieval", min_value=1, max_value=10, value=4, step=1)
show_debug = st.checkbox("Show debug details", value=False)

if st.button("Ask", type="primary"):
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Thinking..."):
            result = ask(question.strip(), top_k=top_k)

        st.subheader("Answer")
        st.write(result.get("answer", ""))

        if show_debug:
            with st.expander("Routing"):
                st.json(result.get("routing", {}))
            with st.expander("SQL Context"):
                st.json(result.get("sql_context", {}))
            with st.expander("Vector Context"):
                st.json(result.get("vector_context", []))
            with st.expander("Prompt Preview"):
                st.text(result.get("prompt_preview", ""))