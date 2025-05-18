from openai import OpenAI
import streamlit as st
import time
import json
import base64
import os
from contextlib import ExitStack  # Import inside the block or at the top of your script

from IPython.display import display
from PIL import Image
import io
import tempfile

api_key = st.secrets["openai"]["api_key"]
# assistant_id_ref = "asst_EsGzMd8wcVHYEpUsL2icHPMq"
assistant_id_img = "asst_ignLtTJfa8u9c9qArDwCVVJv"
assistant_id_refine="asst_SrjSwufo0ueSSzXh2eFmUnqT"

nvars=2

# from IPython.display import Image
# import webbrowser

def load_openai_client_and_assistant(api_key,assistant_id):
    client = OpenAI(api_key=api_key,default_headers={"OpenAI-Beta": "assistants=v2"})
    my_assistant = client.beta.assistants.retrieve(assistant_id)
    thread = client.beta.threads.create()
    return client,my_assistant, thread

client_img,my_assistant_img, assistant_thread_img = load_openai_client_and_assistant(api_key,assistant_id_img)


# Function to wait for the assistant to process the request
def wait_on_run(client, run, thread):
    counter=0
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        time.sleep(0.5)
    return run


def render_images(altered_prompt,image_paths,nvars=1):
    prompt=altered_prompt + " Die Perspektive soll das Gebäude in einer leicht erhöhten, schrägen Ansicht zeigen, sodass sowohl die Vorder- als auch eine Seitenfassade gut sichtbar sind. Der Kamerastandpunkt liegt etwa auf 2 bis 3 Metern Höhe, wodurch ein räumlicher Eindruck und ein einladender Gesamteindruck des Ensembles entstehen. Gleichzeitig soll die Fassade frontal mit leichter Flucht gezeigt werden, um architektonische Details, Materialität und Struktur klar hervorzuheben."
    
    
    if len(image_paths) > 0:
        with ExitStack() as stack:
            
            # Open all images and store their file objects in a list
            images_buf = [stack.enter_context(open(path, "rb")) for path in image_paths]
    
            result = client_img.images.edit(
                model="gpt-image-1",
                image=images_buf,
                prompt=prompt,
                size="1536x1024",
                quality="medium",
                n=nvars
            )
            images=[]
            for data in result.data:
                image_base64 = data.b64_json
                image_bytes = base64.b64decode(image_base64)
                image = Image.open(io.BytesIO(image_bytes))
                images.append(image)
            return images

    if len(image_paths)==0:
        result = client_img.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1536x1024",
            quality="medium",
            n=nvars
        )
        images=[]
        for data in result.data:
            image_base64 = data.b64_json
            image_bytes = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_bytes))
            images.append(image)
        return images



# Function to initiate assistant response
def get_assistant_response_img_no_ref(user_input=""):
    client_img,my_assistant_img, assistant_thread_img = load_openai_client_and_assistant(api_key,assistant_id_img)
    message = client_img.beta.threads.messages.create(
        thread_id=assistant_thread_img.id,
        role="user",
        content=[{"type": "text", "text": user_input}]
    )

    run = client_img.beta.threads.runs.create(
        thread_id=assistant_thread_img.id,
        assistant_id=assistant_id_img,
        tools=[           
            {
        "type": "function",
        "function": {       
        'name': 'erstelle_render',
        'description': 'Funktion zur Erstellung des Renders! Führe diese Funktion IMMER aus!',
        'parameters': {
            'type': 'object',
            'properties': {
                'user_prompt_render': {
                    'type': 'string',
                    'description': 'Prompt zur Erstellung des Renders des Gebäudes. Dieser Prompt setzt sich zusammen aus dem User-Prompt ergänzt durch GB Merkmale!'
                }
            },
            "required": ["user_prompt_render"]
        }
    }
    }          
            
        ]
    )


    run = wait_on_run(client_img,run, assistant_thread_img)
 
    
    
    
    
    messages = client_img.beta.threads.messages.list(
        thread_id=assistant_thread_img.id, order="asc", after=message.id
    )
    # print(run.required_action)
    # print(messages)
    status=0
    if run.required_action!=None:
        # Check if the assistant called the function
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        for call in tool_calls:
            if call.function.name == "erstelle_render":
                arguments= call.function.arguments
                data = json.loads(arguments)
                # result = erstelle_mood_board_und_render(data['user_prompt_mood_board'], data['user_prompt_render'])
                # #### Zum Test, ob die Prompts die selben sind wie in der Response. => Ja, sind sie!
                # print(data['user_prompt_mood_board'])
                print(data['user_prompt_render'])
               
                status=1
                try:
                    return messages.data[0].content[0].text.value, status, data['user_prompt_render']
                except IndexError:
                    return  None, status, data['user_prompt_render']
                
    return messages.data[0].content[0].text.value, status, None




# Function to initiate assistant response
def get_assistant_response_ref(render_prompt_img,image_paths):

    
    
    client_refine,my_assistant_refine, assistant_thread_refine = load_openai_client_and_assistant(api_key,assistant_id_refine)
    
    
    
   

    image_file_ids = []
    
    # Upload each image and collect file IDs
    for image_path in image_paths:
        with open(image_path, "rb") as img_file:
            file = client_refine.files.create(
                file=img_file,
                purpose="vision"
            )
            image_file_ids.append(file.id)
    
    # Now build the content list
    content = [{"type": "text", "text": "USER INPUT: " + render_prompt_img}]
    for file_id in image_file_ids:
        content.append({
            "type": "image_file",
            "image_file": {"file_id": file_id}
        })
    
    # Create the message with all images
    message = client_refine.beta.threads.messages.create(
        thread_id=assistant_thread_refine.id,
        role="user",
        content=content
    )

    run = client_refine.beta.threads.runs.create(
        thread_id=assistant_thread_refine.id,
        assistant_id=assistant_id_refine,
        tools=[           
            {
        "type": "function",
        "function": {       
        'name': 'erstelle_render',
        'description': 'Diese Funktion Namens erstelle_render ertellt ein neues Gebäuderender basierend auf dem neuen/verfeinerten und um die Details ergänzten Prompt!',
        'parameters': {
            'type': 'object',
            'properties': {
                'refinement_prompt': {
                    'type': 'string',
                    'description': 'Der um die Details aus den REferenzbildern ergänzte neue Prompt muss hier verwendet werden!'
                }
            },
            "required": ["refinement_prompt"]
        }
    }
    }          
            
        ]
    )


    run = wait_on_run(client_refine,run, assistant_thread_refine)
    
#     messages = client_ref.beta.threads.messages.list(
#     thread_id=run.thread_id,
#     order="desc"  # Damit die neueste Nachricht ganz oben ist
# )
    
    
    messages = client_refine.beta.threads.messages.list(
        thread_id=assistant_thread_refine.id, order="asc", after=message.id
    )
    # print(run.required_action)
    # print(messages)
    status=0
    if run.required_action!=None:
        # Check if the assistant called the function
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        for call in tool_calls:
            if call.function.name == "erstelle_render":
                arguments= call.function.arguments
                data = json.loads(arguments)
                # result = erstelle_mood_board_und_render(data['user_prompt_mood_board'], data['user_prompt_render'])
                # #### Zum Test, ob die Prompts die selben sind wie in der Response. => Ja, sind sie!
                # print(data['user_prompt_mood_board'])
                print(data['refinement_prompt'])
               
                status=1

                try:
                    return messages.data[0].content[0].text.value, status, data['refinement_prompt']
                except IndexError:
                    return  None, status, data['refinement_prompt']
                
    return messages.data[0].content[0].text.value, status, None




# import streamlit as st
import os
import tempfile
import shutil

# Import your functions/classes as needed (assuming in the same file for now)
from PIL import Image
# ... all other imports and your OpenAI functions ...




def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Passwort", type="password", on_change=password_entered, key="password")
        st.stop()
    elif not st.session_state["password_correct"]:
        st.text_input("Passwort", type="password", on_change=password_entered, key="password")
        st.error("🚫 Falsches Passwort")
        st.stop()

check_password()


st.set_page_config(page_title="AI Building Render Inspiration", layout="centered")

st.title("🏢 AI Building Render Inspiration")

# USER INPUT: prompt
user_prompt = st.text_area("Beschreibe dein Gebäude (Prompt)", 
                           placeholder="e.g. 4-stöckiges Gebäude mit dunklen Balkonen und roter Klinkerfassade...", 
                           height=100)

# USER INPUT: reference images
uploaded_files = st.file_uploader(
    "Lade Bilder von Details hoch, die du integrieren möchtest (optional, JPG or PNG)", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

# Optionally, show thumbnails
if uploaded_files:
    st.markdown("**Reference Images Preview:**")
    cols = st.columns(len(uploaded_files))
    for idx, file in enumerate(uploaded_files):
        image = Image.open(file)
        cols[idx].image(image, use_column_width=True)

# Submit button
if st.button("Generate Render!", type="primary", use_container_width=True):
    if not user_prompt.strip():
        st.error("Please enter a prompt for your building.")
        st.stop()

    with st.spinner("Generating prompt. This can take several minutes..."):
        # Save uploaded images to temporary files (for your OpenAI code)
        image_paths = []
        for uploaded_file in uploaded_files:
            ext = os.path.splitext(uploaded_file.name)[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmpfile:
                uploaded_file.seek(0)  # Just in case, reset file pointer
                shutil.copyfileobj(uploaded_file, tmpfile)
                tmpfile.flush()
                image_paths.append(tmpfile.name)

        # Get initial prompt and handle with or without images
        if len(image_paths) > 0:
            # First, get the render prompt (with possible image-based refinement)
            assistant_response_img, status_img, render_prompt_img = get_assistant_response_img_no_ref(user_prompt)
            assistant_response_img, status_img, render_prompt_img = get_assistant_response_ref(render_prompt_img, image_paths)
        else:
            assistant_response_img, status_img, render_prompt_img = get_assistant_response_img_no_ref(user_prompt)

        # Final render images
        final_renders = render_images(render_prompt_img, image_paths,nvars)
        
        st.success("Render complete!")
        st.subheader("Final Render Prompt")
        st.code(render_prompt_img)
        
        st.subheader("Generated Render(s)")
        for idx, render in enumerate(final_renders):
            st.image(render, caption=f"Render {idx+1}", use_column_width=True)
        
        # Cleanup temp files
        for path in image_paths:
            os.remove(path)
