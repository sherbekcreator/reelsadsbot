import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.future import select

from database import engine, Base, AsyncSessionLocal, User, Transaction

# --- SOZLAMALAR ---
BOT_TOKEN = "8252237845:AAFUpoc-GaH7QZmRbq0CNesvB879YvHe-AM"

# DIQQAT: Agar tunnel o'chib qolgan bo'lsa, shu yerdagi havolani yangisiga almashtirasiz.
# Hozirgi holatda keshni tozalash uchun oxiriga /?v=5 qo'shildi.
MINI_APP_URL = "https://ae2b2c1b489c8b.lhr.life/?v=5" 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- BAZANI ISHGA TUSHIRISH ---
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- AIOGRAM: TELEGRAM BOT MANTIG'I (REFERAL BILAN) ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    tg_id = message.from_user.id
    full_name = message.from_user.full_name
    lang = message.from_user.language_code
    
    # Deep link orqali kelgan Referal ID ni aniqlaymiz
    referrer_id = None
    if command.args and command.args.isdigit():
        referrer_id = int(command.args)
        if referrer_id == tg_id:
            referrer_id = None # O'ziga o'zi referal bo'lolmaydi
            
    async with AsyncSessionLocal() as session:
        # Foydalanuvchini bazadan tekshirish
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalars().first()
        
        # Agar yangi foydalanuvchi bo'lsa
        if not user:
            user = User(tg_id=tg_id, full_name=full_name, language_code=lang, referred_by=referrer_id)
            session.add(user)
            
            # Agar kimdir taklif qilgan bo'lsa, unga bonus beramiz (Masalan: 50,000 koin)
            if referrer_id:
                ref_result = await session.execute(select(User).where(User.tg_id == referrer_id))
                referrer = ref_result.scalars().first()
                if referrer:
                    referrer.balance += 50000
                    referrer.total_earned += 50000
                    
                    # Tranzaksiya yozamiz
                    new_tx = Transaction(user_id=referrer.id, tx_type="referral_bonus", amount=50000, description="Yangi do'st taklif qilindi")
                    session.add(new_tx)
                    
                    # Taklif qilgan odamga xabar yuboramiz
                    try:
                        await bot.send_message(
                            referrer_id, 
                            f"🎉 Tabriklaymiz!\n\nDo'stingiz ({full_name}) sizning havolangiz orqali kirdi va sizga 50,000 🪙 bonus berildi!"
                        )
                    except:
                        pass
                        
            await session.commit()

    # Botning username'ini olamiz (Taklif havolasini yasash uchun)
    bot_info = await bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={tg_id}"
            
    # Xush kelibsiz xabari (Endi taklif havolasi bilan)
    text = (
        f"👋 Salom, {full_name}!\n\n"
        "ReelAds platformasiga xush kelibsiz!\n"
        "• Reels tomosha qiling va koin to'plang.\n"
        "• 10,000 Koin = $1.00\n"
        "• Minimal yechish: $5 (50,000 koin)\n\n"
        f"🔗 **Sizning shaxsiy taklif havolangiz:**\n`{invite_link}`\n"
        "(Har bir do'stingiz uchun 50,000 koin oling!)\n\n"
        "Boshlash uchun pastdagi tugmani bosing 👇"
    )
    
    # Tugmalar
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Mini App ni ochish", web_app=WebAppInfo(url=MINI_APP_URL))],
            [InlineKeyboardButton(text="📢 Do'stlarga ulashish", switch_inline_query=f"ReelAds orqali pul ishlang! Shu havola orqali kiring: {invite_link}")]
        ]
    )
    
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

# --- FASTAPI: API VA LIFESPAN (Yashash sikli) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(dp.start_polling(bot))
    yield
    task.cancel()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def serve_mini_app():
    return FileResponse("index.html")

@app.get("/api/user/{tg_id}")
async def get_user_info(tg_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
        return {"tg_id": user.tg_id, "balance": user.balance, "total_earned": user.total_earned}

@app.post("/api/reward")
async def add_reward(request: Request):
    data = await request.json()
    tg_id = data.get("tg_id")
    amount = data.get("amount")
    tx_type = data.get("tx_type")
    
    if not tg_id or not amount:
        raise HTTPException(status_code=400, detail="Ma'lumot to'liq emas")
        
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
        
        user.balance += amount
        user.total_earned += amount
        new_tx = Transaction(user_id=user.id, tx_type=tx_type, amount=amount, description=f"{tx_type} bajarildi")
        session.add(new_tx)
        await session.commit()
        return {"status": "success", "new_balance": user.balance}