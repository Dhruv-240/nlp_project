import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")

hide_streamlit_style = """
<style>
.st-emotion-cache-zy6yx3 {
    padding-bottom: 0;
 
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
import os
import database as db
import arxiv
import datetime
import requests
import base64
import google.generativeai as genai
from dotenv import load_dotenv
from PyPDF2 import PdfReader



# --- Configuration ---
SAVED_PAPERS_DIR = "saved_papers"
os.makedirs(SAVED_PAPERS_DIR, exist_ok=True)


# --- Gemini API Setup ---
def get_gemini_model():
    """Initializes and returns the Gemini Pro model."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel('gemini-2.5-flash')
        except Exception as e:
            st.error(f"Failed to configure Gemini API: {e}")
            return None
    return None


# --- UI Rendering ---
def show_login_signup():
    conn = db.create_connection()
    db.create_table(conn)

    st.markdown("<h1 style='text-align: center;'>Welcome to the Research Paper AI</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,1.5,1])

    with col2:
        with st.container(border=True):
            choice = st.radio("Choose an action", ['Login', 'Sign Up'], horizontal=True)

            if choice == 'Sign Up':
                st.subheader("Create a New Account")
                new_username = st.text_input("Choose a username")
                new_password = st.text_input("Choose a password", type="password")
                if st.button("Sign Up"):
                    if not new_username or not new_password:
                        st.error("Username and password cannot be empty.")
                    elif db.add_user(conn, new_username.lower(), new_password):
                        user_folder = os.path.join(SAVED_PAPERS_DIR, new_username.lower())
                        os.makedirs(user_folder, exist_ok=True)
                        st.session_state.username = new_username.lower()
                        st.session_state.page = 'retrieval'
                        st.rerun()
                    else:
                        st.error("Username already exists.")

            elif choice == 'Login':
                st.subheader("Log Into Your Account")
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.button("Login"):
                    if db.check_user(conn, username.lower(), password):
                        st.session_state.username = username.lower()
                        st.session_state.page = 'retrieval'
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

def show_retrieval_page():
    if 'username' not in st.session_state:
        st.session_state.page = 'login'
        st.rerun()
        return
    st.title("Paper Retrieval")
    
    # --- Sidebar ---
    username = st.session_state.username
    user_folder = os.path.join(SAVED_PAPERS_DIR, username)
    st.sidebar.subheader("Your Saved Papers:")
    if os.path.exists(user_folder):
        saved_files = [f for f in os.listdir(user_folder) if not f.endswith('.chat.json')]
        paper_titles = sorted(list(set([os.path.splitext(f)[0] for f in saved_files])))
        if paper_titles:
            for title in paper_titles:
                col1, col2, col3 = st.sidebar.columns([0.6, 0.2, 0.2])
                with col1:
                    if st.button(title, key=f"sidebar_retrieval_{title}"):
                        txt_path = os.path.join(user_folder, f"{title}.txt")
                        pdf_path = os.path.join(user_folder, f"{title}.pdf")
                        
                        if os.path.exists(txt_path):
                            with open(txt_path, "r") as f:
                                content = f.read()
                            try:
                                # Extract data from the text file
                                title_from_file = content.split("\n")[0].replace("Title: ", "")
                                authors_str = content.split("\n")[1].replace("Authors: ", "")
                                authors = authors_str.split(", ")
                                pdf_url_from_file = content.split("\n")[2].replace("PDF_URL: ", "")
                                summary = content.split("--- Summary ---")[1].split("--- Drawbacks ---")[0].strip()
                                drawbacks = content.split("--- Drawbacks ---")[1].split("--- Full Text ---")[0].strip()
                                full_text = content.split("--- Full Text ---")[1].strip()

                                st.session_state.selected_paper = {
                                    'title': title_from_file,
                                    'summary': summary,
                                    'authors': authors,
                                    'published': 'N/A', # This info is not in the txt
                                    'pdf_url': pdf_url_from_file,
                                    'drawbacks': drawbacks,
                                    'full_text': full_text
                                }
                                if os.path.exists(pdf_path):
                                    st.session_state.selected_paper['pdf_local_path'] = pdf_path

                                st.session_state.page = 'chat'
                                if 'messages' in st.session_state: del st.session_state['messages']

                                # Load chat history if it exists
                                safe_title = "".join(c for c in title_from_file if c.isalnum() or c in (' ', '_')).rstrip()
                                chat_filename = f"{safe_title}.chat.json"
                                chat_filepath = os.path.join(user_folder, chat_filename)
                                if os.path.exists(chat_filepath):
                                    with open(chat_filepath, "r") as f:
                                        st.session_state.messages = json.load(f)
                                else:
                                    st.session_state.messages = []

                                st.rerun()

                            except IndexError:
                                st.error("Could not parse the saved paper file.")
                with col2:
                    pdf_path = os.path.join(user_folder, f"{title}.pdf")
                    if os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            st.download_button("⬇️", f, file_name=f"{title}.pdf", key=f"download_retrieval_{title}")
                with col3:
                    if st.button("🗑️", key=f"delete_retrieval_{title}"):
                        txt_path = os.path.join(user_folder, f"{title}.txt")
                        pdf_path = os.path.join(user_folder, f"{title}.pdf")
                        chat_path = os.path.join(user_folder, f"{title}.chat.json")
                        if os.path.exists(txt_path):
                            os.remove(txt_path)
                        if os.path.exists(pdf_path):
                            os.remove(pdf_path)
                        if os.path.exists(chat_path):
                            os.remove(chat_path)
                        st.rerun()
        else:
            st.sidebar.write("No papers saved yet.")
            
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.write(f"Hello, {username}")
    with col2:
        if st.button("Logout", key="logout_retrieval"):
            st.session_state.clear()
            st.rerun()

    # --- Main Page Content ---
    st.write(f"Welcome, {st.session_state.username}! Find papers on arXiv.")
    with st.form(key='search_form'):
        search_query = st.text_input("Search for papers", "quantum computing")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date (optional)", None)
        with col2:
            end_date = st.date_input("End date (optional)", datetime.date.today())

        col3, col4 = st.columns(2)
        with col3:
            max_results = st.number_input("Number of papers", 1, 100, 10)
        with col4:
            sort_options = {
                "Relevance": arxiv.SortCriterion.Relevance,
                "Last Updated Date": arxiv.SortCriterion.LastUpdatedDate,
                "Submitted Date": arxiv.SortCriterion.SubmittedDate
            }
            sort_by_display = st.selectbox("Sort by", list(sort_options.keys()))
            sort_by = sort_options[sort_by_display]

        submit_button = st.form_submit_button(label='Search')

    if submit_button:
        final_query = search_query
        if start_date and end_date:
            date_query = f'submittedDate:[{start_date.strftime("%Y%m%d")} TO {end_date.strftime("%Y%m%d")}]'
            final_query = f'({search_query}) AND {date_query}'
        
        client = arxiv.Client()
        search = arxiv.Search(query=final_query, max_results=max_results, sort_by=sort_by)
        results = list(client.results(search))
        st.session_state.search_results = results

    if 'search_results' in st.session_state:
        st.subheader("Search Results")

        # Get a list of saved paper titles
        saved_paper_titles = []
        if os.path.exists(user_folder):
            saved_files = os.listdir(user_folder)
            saved_paper_titles = [os.path.splitext(f)[0] for f in saved_files]
        
        for i, result in enumerate(st.session_state.search_results):
            with st.container(border=True):
                col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
                with col1:
                    st.subheader(result.title)
                    st.write(f"**Authors:** {', '.join(a.name for a in result.authors)}")
                
                safe_title = "".join(c for c in result.title if c.isalnum() or c in (' ', '_')).rstrip()
                is_saved = safe_title in saved_paper_titles

                with col2:
                    if is_saved:
                        st.button("Saved", key=f"saved_{result.entry_id}_{i}", disabled=True)
                    else:
                        if st.button("Save", key=f"save_{result.entry_id}_{i}"):
                            model = get_gemini_model()
                            if model:
                                with st.spinner("Saving this may take a moment..."):
                                    # --- Generate Summary ---
                                    summary_response = model.generate_content(f"Summarize this research paper: {result.summary}")
                                    gemini_summary = summary_response.text

                                    # --- Find Drawbacks ---
                                    drawbacks_response = model.generate_content(f"Analyze this research paper and identify its limitations and drawbacks: {result.summary}")
                                    gemini_drawbacks = drawbacks_response.text

                                    # --- Save PDF and Extract Text ---
                                    try:
                                        pdf_response = requests.get(result.pdf_url)
                                        pdf_response.raise_for_status()
                                        paper_filename_pdf = f"{safe_title}.pdf"
                                        pdf_path = os.path.join(user_folder, paper_filename_pdf)
                                        with open(pdf_path, "wb") as f:
                                            f.write(pdf_response.content)

                                        # --- Extract Text from PDF ---
                                        with open(pdf_path, "rb") as f:
                                            reader = PdfReader(f)
                                            full_text = "".join(page.extract_text() for page in reader.pages)

                                        # --- Save Text File ---
                                        paper_content = f"Title: {result.title}\nAuthors: {', '.join(a.name for a in result.authors)}\nPDF_URL: {result.pdf_url}\n\n--- Summary ---\n{gemini_summary}\n\n--- Drawbacks ---\n{gemini_drawbacks}\n\n--- Full Text ---\n{full_text}"
                                        paper_filename_txt = f"{safe_title}.txt"
                                        with open(os.path.join(user_folder, paper_filename_txt), "w") as f:
                                            f.write(paper_content)

                                        st.success(f"Saved and analyzed '{result.title}'")
                                        st.rerun()
                                    except Exception as e:
                                        st.warning(f"Could not download or process PDF for '{result.title}': {e}")
                            else:
                                st.error("Please enter your Gemini API key in the .env file.")


def show_chat_page():
    if 'username' not in st.session_state:
        st.session_state.page = 'login'
        st.rerun()
        return
    username = st.session_state.username
    paper = st.session_state.selected_paper

    # --- Sidebar ---
    if st.sidebar.button("<- Back to Search"):
        st.session_state.page = 'retrieval'
        if 'selected_paper' in st.session_state: del st.session_state['selected_paper']
        if 'search_results' in st.session_state: del st.session_state['search_results']
        if 'messages' in st.session_state: del st.session_state['messages']
        st.rerun()
        
    st.sidebar.subheader("Your Saved Papers:")
    user_folder = os.path.join(SAVED_PAPERS_DIR, username)
    if os.path.exists(user_folder):
        saved_files = [f for f in os.listdir(user_folder) if not f.endswith('.chat.json')]
        paper_titles = sorted(list(set([os.path.splitext(f)[0] for f in saved_files])))
        if paper_titles:
            for title in paper_titles:
                col1, col2, col3 = st.sidebar.columns([0.6, 0.2, 0.2])
                with col1:
                    if st.button(title, key=f"sidebar_chat_{title}"):
                        txt_path = os.path.join(user_folder, f"{title}.txt")
                        pdf_path = os.path.join(user_folder, f"{title}.pdf")
                        
                        if os.path.exists(txt_path):
                            with open(txt_path, "r") as f:
                                content = f.read()
                            try:
                                title_from_file = content.split("\n")[0].replace("Title: ", "")
                                authors_str = content.split("\n")[1].replace("Authors: ", "")
                                authors = authors_str.split(", ")
                                pdf_url_from_file = content.split("\n")[2].replace("PDF_URL: ", "")
                                summary = content.split("--- Summary ---")[1].split("--- Drawbacks ---")[0].strip()
                                drawbacks = content.split("--- Drawbacks ---")[1].split("--- Full Text ---")[0].strip()
                                full_text = content.split("--- Full Text ---")[1].strip()

                                st.session_state.selected_paper = {
                                    'title': title_from_file,
                                    'summary': summary,
                                    'authors': authors,
                                    'published': 'N/A',
                                    'pdf_url': pdf_url_from_file,
                                    'drawbacks': drawbacks,
                                    'full_text': full_text
                                }
                                
                                if os.path.exists(pdf_path):
                                    st.session_state.selected_paper['pdf_local_path'] = pdf_path

                                if 'messages' in st.session_state: del st.session_state['messages']

                                # Load chat history if it exists
                                safe_title = "".join(c for c in title_from_file if c.isalnum() or c in (' ', '_')).rstrip()
                                chat_filename = f"{safe_title}.chat.json"
                                chat_filepath = os.path.join(user_folder, chat_filename)
                                if os.path.exists(chat_filepath):
                                    with open(chat_filepath, "r") as f:
                                        st.session_state.messages = json.load(f)
                                else:
                                    st.session_state.messages = []

                                st.rerun()

                            except IndexError:
                                st.error("Could not parse the saved paper file.")
                with col2:
                    pdf_path = os.path.join(user_folder, f"{title}.pdf")
                    if os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            st.download_button("⬇️", f, file_name=f"{title}.pdf", key=f"download_chat_{title}")
                with col3:
                    if st.button("🗑️", key=f"delete_chat_{title}"):
                        txt_path = os.path.join(user_folder, f"{title}.txt")
                        pdf_path = os.path.join(user_folder, f"{title}.pdf")
                        chat_path = os.path.join(user_folder, f"{title}.chat.json")
                        if os.path.exists(txt_path):
                            os.remove(txt_path)
                        if os.path.exists(pdf_path):
                            os.remove(pdf_path)
                        if os.path.exists(chat_path):
                            os.remove(chat_path)
                        st.rerun()
        else:
            st.sidebar.write("No papers saved yet.")
    
    st.sidebar.write("---") # Using a divider for better separation
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.write(f"Hello, {username}")
    with col2:
        if st.button("Logout", key="logout_chat"):
            st.session_state.clear()
            st.rerun()


    # --- Main Page Content ---
    st.subheader(paper['title'])
    st.caption(f"Authors: {', '.join(paper['authors'])} ")
    
    with st.expander("View Paper Summary"):
        st.write(paper['summary'])

    with st.expander("View Paper Drawbacks"):
        st.write(paper['drawbacks'])
    
    st.divider()

    left_col, right_col = st.columns(2)

    # --- Left Column: PDF Viewer ---
    with left_col:
        st.markdown("##### Paper PDF")
        pdf_displayed = False
        # --- Try to load local PDF first ---
        if 'pdf_local_path' in paper and paper['pdf_local_path']:
            try:
                with open(paper['pdf_local_path'], "rb") as f:
                    pdf_bytes = f.read()
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="400" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
                pdf_displayed = True
            except FileNotFoundError:
                st.warning("Saved PDF not found. Trying to fetch from URL.")
            except Exception as e:
                st.error(f"An error occurred while loading the local PDF: {e}")

        # --- Fallback to URL if local PDF not displayed ---
        if not pdf_displayed and paper['pdf_url']:
            try:
                response = requests.get(paper['pdf_url'])
                response.raise_for_status()
                pdf_bytes = response.content
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="5000" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
            except requests.exceptions.RequestException as e:
                st.error(f"Failed to load PDF from URL: {e}")
            except Exception as e:
                st.error(f"An error occurred: {e}")
        elif not pdf_displayed:
            st.info("No PDF available for this paper.")

    # --- Right Column: Chat Interface ---
    with right_col:
        st.markdown("##### Chat")

        if st.button("Clear Chat", key="clear_chat_button"):
            if 'messages' in st.session_state:
                st.session_state.messages = []
            # Also delete the chat history file
            safe_title = "".join(c for c in paper['title'] if c.isalnum() or c in (' ', '_')).rstrip()
            chat_filename = f"{safe_title}.chat.json"
            chat_filepath = os.path.join(SAVED_PAPERS_DIR, username, chat_filename)
            if os.path.exists(chat_filepath):
                os.remove(chat_filepath)
            st.rerun()

        if "messages" not in st.session_state:
            st.session_state.messages = []

        with st.container(height=350, border=True):
            for message in st.session_state.messages:
                role = message["role"]
                if role == "model":
                    role = "assistant"
                with st.chat_message(role):
                    st.markdown(message["content"])

            if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                with st.chat_message("assistant"):
                    placeholder = st.empty()
                    full_response = ""
                    model = get_gemini_model()
                    if model:
                        history = []
                        history.append({"role": "user", "parts": [f"Here is the paper I am asking about:\n\nTitle: {paper['title']}\n\nFull Text (truncated to 16000 characters):\n{paper['full_text'][:16000]} "]})
                        for msg in st.session_state.messages:
                            role = msg["role"]
                            if role == "assistant":
                                role = "model"
                            history.append({"role": role, "parts": [msg["content"]]})
                        
                        response = model.generate_content(history, stream=True)

                        for chunk in response:
                            try:
                                full_response += chunk.text
                                placeholder.markdown(full_response + "▌")
                            except ValueError:
                                pass
                        placeholder.markdown(full_response)
                        st.session_state.messages.append({"role": "model", "content": full_response})
                    else:
                        full_response = "Please enter your Gemini API key to use the chat."
                        placeholder.markdown(full_response)
                        st.session_state.messages.append({"role": "model", "content": full_response})

                    # Save the updated chat history
                    safe_title = "".join(c for c in paper['title'] if c.isalnum() or c in (' ', '_')).rstrip()
                    chat_filename = f"{safe_title}.chat.json"
                    chat_filepath = os.path.join(SAVED_PAPERS_DIR, username, chat_filename)
                    with open(chat_filepath, "w") as f:
                        json.dump(st.session_state.messages, f)

        if prompt := st.chat_input("Ask questions about the paper..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.rerun()



# --- App Entry Point ---
if __name__ == "__main__":
    if 'page' not in st.session_state:
        st.session_state.page = 'login'

    if st.session_state.page == 'login':
        show_login_signup()
    elif st.session_state.page == 'retrieval':
        show_retrieval_page()
    elif st.session_state.page == 'chat':
        show_chat_page()
