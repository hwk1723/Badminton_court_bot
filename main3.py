from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage

from telethon.sync import TelegramClient, events
from telethon.tl.types import PeerChannel, Channel
import asyncio
import os
from dotenv import load_dotenv

conversation_history = {}

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
phone_number = os.getenv("PHONE_NUMBER")

# target_channel_id = 1826858168  # SG BADMINTON COURT
# target_channel_id = 2098799554 # Sg courts swapping 🤝🫶
target_channel_id = [2803244639] # test group
# target_channel_id = [1826858168, 2098799554]
bot_control_group_id = -4904086965

KEYWORD = ['pasir ris', 'meridian', 'park view', 'casurina pri']

listening_enabled = False  # Control switch

# with TelegramClient('session_name', api_id, api_hash) as client:
#     for dialog in client.get_dialogs():
#         print(f"{dialog.name} — ID: {dialog.id} — Username: {getattr(dialog.entity, 'username', None)}")
# exit()

model = ChatOpenAI(model="gpt-4o", openai_api_key=api_key)


async def main():

    async with TelegramClient('session_name', api_id, api_hash) as client:
        await client.start(phone=phone_number)

        @client.on(events.NewMessage(chats=bot_control_group_id))
        async def toggle_listener(event):
            global listening_enabled
            message_text = event.message.message.strip().upper()
            if message_text == "ON":
                listening_enabled = True
                print("[CONTROL] Listening enabled.")
            elif message_text == "OFF":
                listening_enabled = False
                print("[CONTROL] Listening disabled.")

        @client.on(events.NewMessage)
        async def handler(event):
            if not listening_enabled:
                return

            # print(event.message.peer_id)
            
            peer = event.message.peer_id
            if not isinstance(peer, PeerChannel) or peer.channel_id not in target_channel_id:
                return

            message = event.message.message

            if any(keyword.lower() in message.lower() for keyword in KEYWORD) and "look" not in message.lower():
                user = await event.get_sender()
                user_id = user.id
                print(f"[FOUND] : {message}")
                
                # Dynamically create the system prompt after message is validated
                system_prompt = SystemMessage(
                    content=f"""
                    You're a booking assistant who helps buyers to purchase badminton court offers. The user you are conversing with is the seller and will be only asking about the court availability, price, and payment method. This is the details of the court: {message}

                    Always ask for these 3 information in this order:

                    1) Ask about the availability of the court.
                    2) If the price is NOT indicated in {message}, then ask about the price. (Ask only if price is not stated).

                    Once the availability and price is confirmed, then:

                    3) Ask about the payment method.

                    Respond only with the questions, do not provide any other information.

                    If there is more than one sessions available, always choose the latest one.
                    
                    Always end off the conversation by thanking the seller after payment method is confirmed.
                    """
                )
                try:
                    await client.send_message(user, f"Hello! I'm interested in:\n\n{message}")
                    conversation_history[user_id] = [system_prompt]
                except Exception as e:
                    print(f"❌ Failed to message user ID {user_id}: {e}")

        @client.on(events.NewMessage)
        async def user_reply_handler(reply_event):
            sender = await reply_event.get_sender()
            user_id = sender.id

            if user_id not in conversation_history:
                return  # Skip if we haven’t initiated conversation with this user

            reply_text = reply_event.message.message
            history = conversation_history.get(user_id, [])
            history.append(HumanMessage(content=reply_text))
            # The first message in history is the system prompt
            if history and isinstance(history[0], SystemMessage):
                system_prompt = history[0]
                rest_history = history[1:]
            else:
                system_prompt = None
                rest_history = history

            response = model.invoke(([system_prompt] if system_prompt else []) + rest_history)
            ai_reply = response.content
            history.append(AIMessage(content=ai_reply))
            conversation_history[user_id] = history

            await client.send_message(sender, ai_reply)

            if "thank" in ai_reply.lower():
                print(f"[INFO] Conversation with user {user_id} ended.")
                del conversation_history[user_id]
                # await client.disconnect()

        print("Listening...")
        await client.run_until_disconnected()

asyncio.run(main())