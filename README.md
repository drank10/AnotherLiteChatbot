<img src="AnotherLiteChatbot.jpg">

## Overview
This is a light AI chatbot interface. It uses the Piper TTS engine and Whisper.cpp. The LLM can be hosted using LM Studio or Ollama

## Features
- **Fast response time:** Real-Time speech without having to hit record or play
- **Avatar in image or video format**
- **Avatar is output to a webserver** 


## Requirements
- Python 3.x
- LM Studio or Ollama hosting the LLM
- Whisper-cli.exe in project folder - https://github.com/ggerganov/whisper.cpp/actions/runs/13173996633
- Piper.exe in project folder - https://github.com/rhasspy/piper/releases/tag/2023.11.14-2
- Other dependencies listed in `requirements.txt`

## Installation

1. Create Python environment and then clone the repository:
   ```bash
   git clone https://github.com/drank10/AnotherLiteChatbot.git
   cd AnotherLiteChatbot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the program:
   ```bash
   python main.py
   ```

## Usage

1. **Set a system prompt:** Manually enter system prompt for character profile or select from file 
2. **Start Chatting:** Press the Start button to start chatting or enter a text message
3. **Set Avatar** to an image, animated GIF or video file
4. **Stop Chatting** Say Exit to quit program
   
## Customization
- You can modify the TTS voice models, system prompts, and other settings through the interface or by editing the source code.
- Different models of STT (Whisper Tiny), TTS voice quality and LLM size can be used to adjust performance and used VRAM.
- Avatar GIF\Video can be reached at http://127.0.0.1:5000/. Set to 0.0.0.0 and configure firewall if needed to display on other machines. 

## Contributing
Feel free to fork this repository and submit pull requests! If you encounter any issues, please create an issue on GitHub.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
```
