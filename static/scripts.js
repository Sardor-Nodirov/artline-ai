const input = document.getElementById('userInput');

    input.addEventListener('keyup', function(event) {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });

function sendMessage() {
    
    const userInput = document.getElementById('userInput');
    const chatHistory = document.getElementById('chatHistory');

    // Prevent sending an empty message
    if (userInput.value.trim() === '') {
        return;
    }

    const userDIV = document.createElement('div')
    userDIV.classList.add('user-div')

    const userMessage = document.createElement('div');
    userMessage.classList.add('user', 'message');

    const userText = document.createElement('span');
    userText.textContent = userInput.value;
    userMessage.appendChild(userText);
    userDIV.appendChild(userMessage)

    const userIcon = document.createElement('div');
    userIcon.classList.add('user-icon');
    userDIV.appendChild(userIcon);

    const userTime = document.createElement('span');
    userTime.classList.add('time-text-user');
    userTime.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });  // Current time

    chatHistory.appendChild(userDIV);
    chatHistory.appendChild(userTime);

    chatHistory.scrollTop = chatHistory.scrollHeight;


    // Fetch user's IP address
    fetch('https://api.ipify.org?format=json')
        .then(response => response.json())
        .then(data => {
            const userIP = data.ip;

            // Fetch response from server
            fetch('/get_response', {
                method: 'POST',
                body: JSON.stringify({
                    message: userInput.value,
                    ip: userIP  // Send IP along with the message
                }),
                headers: {
                    'Content-Type': 'application/json'
                }
            })
    .then(response => response.json())  // Convert the response to JSON
    .then(data => {

        const ai_DIV = document.createElement('div')
        ai_DIV.classList.add('ai-div')

        const assistantMessage = document.createElement('div');
        assistantMessage.classList.add('assistant', 'message');

        const assistantText = document.createElement('span');
        assistantText.textContent = data['response'];
        assistantMessage.appendChild(assistantText);
        ai_DIV.appendChild(assistantMessage)

        const assistantIcon = document.createElement('div');
        assistantIcon.classList.add('assistant-icon');
        ai_DIV.appendChild(assistantIcon);

        const assistantTime = document.createElement('span');
        assistantTime.classList.add('time-text-ai');
        assistantTime.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });  // Current time

        chatHistory.appendChild(ai_DIV);
        chatHistory.appendChild(assistantTime);

        chatHistory.scrollTop = chatHistory.scrollHeight;
    });

    // Clear the input
    userInput.value = '';
})}
