
![Logo](https://i.imgur.com/JIdpA0Q.png)
 <p align="center">

# 🎮 GamePulse Steam Discord Bot 🌟

GamePulse uses Python-A2S to Query Steam Game Servers and updates Voice Channels based on their status. If you want a simple bot that will display Game Server Status info at a glance, check this out! 

# ✨ Created with Python and ChatGPT! ✨ 

</p>

 <p align="center">
    <a href="https://github.com/Ynd21/GamePulse-Steam-Discord-Bot/issues">Report Bug</a>
    .
    <a href="https://github.com/Ynd21/GamePulse-Steam-Discord-Bot/issues">Request Feature</a>
  </p>


![Contributors](https://img.shields.io/github/contributors/Ynd21/GamePulse-Steam-Discord-Bot?color=dark-green) ![Forks](https://img.shields.io/github/forks/Ynd21/GamePulse-Steam-Discord-Bot?style=social) ![Stargazers](https://img.shields.io/github/stars/Ynd21/GamePulse-Steam-Discord-Bot?style=social) ![Issues](https://img.shields.io/github/issues/Ynd21/GamePulse-Steam-Discord-Bot) ![License](https://img.shields.io/github/license/Ynd21/GamePulse-Steam-Discord-Bot) 


## Features

- Easy to use WebUI
- Manage Servers, View History, Look at Leaderboards via the Web!
- Updates Discord Voice Channels with Server Status and Player Count every 2 minutes
- Embeds a Message in a Text Channel Displaying Server Information (Status, Players, Quick Join URL)
- Add Servers via Slash Commands and look at Server History


## Contributing

Contributions are always welcome! Submit a request! 


## Screenshots

<table width="100%">
  <thead>
    <tr>
      <th width="50%">Discord</th>
      <th width="50%">WebUI</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td width="50%"><img src="https://i.imgur.com/tZw0LMy.png"/></td>
      <td width="50%"><img src="https://i.imgur.com/cZVYTsg.png"/></td>
    </tr>
<tr>
	<td width="50%"><img src="https://i.imgur.com/jwmT3C9.png"/></td>
      <td width="50%"><img src="https://i.imgur.com/0KQj2pa.gif"/></td>
</tr>
    <tr>
      <td width="50%"><img src="https://i.imgur.com/Myd3h8Y.png"/></td>
      <td width="50%"><img src="https://i.imgur.com/UUQDolS.png"/></td>
    </tr>	  
  </tbody>
</table>
![](https://i.imgur.com/0KQj2pa.gif)

## Tech Stack

python, py-cord, flask, bootstrap, [Creative Tim](https://www.creative-tim.com/)


## Run the bot

Clone the project

```bash
  git clone https://github.com/Ynd21/GamePulse-Steam-Discord-Bot
```

Go to the project directory

```bash
  cd GamePulse-Steam-Discord-Bot
```

Install dependencies

```bash
  pip install -r requirements.txt
```

Edit Settings.ini

```ini
[DISCORD]
token = Your Discord Token
channel_id = Channel ID to post Server Status 
status_image = Banner Image Used for the Embed from above
guild_id = Discord Guild ID 
allowed_user_ids = Discord User ID, seperated by a coma 
client_id = Discord Bot Client ID
client_secret = Discord Bot Secret
redirect_uri = Discord Bot Redirect URL
avatar = assets/lol.png (default - add anything you want into the assets folder, ref it here for the avatar image)
bot_username = Bots Name
bot_version = Just a Number
community_name = Your Community Name
```

Start the server

```bash
  python bot.py
```

