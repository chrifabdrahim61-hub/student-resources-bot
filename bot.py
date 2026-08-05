import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from database import init_db, get_children, get_section, get_db

# ==================== CONFIG ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ITEMS_PER_PAGE = 10
# =================================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


def build_keyboard(parent_id=None, page=0):
    """
    Build keyboard with mixed layout:
    - Content items: 2 per row (like screenshot)
    - Navigation: 1 per row (full width)
    """
    all_items = get_children(parent_id)
    per_page = ITEMS_PER_PAGE
    start = page * per_page
    end = start + per_page
    items = all_items[start:end]
    total = len(all_items)
    
    buttons = []
    
    # Content items: 2 per row
    row = []
    for item in items:
        display = f"{item['emoji']} {item['title']}"
        callback_data = f"open:{item['id']}:0"
        row.append(InlineKeyboardButton(display, callback_data=callback_data))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    # Add remaining item (if odd number)
    if row:
        buttons.append(row)
    
    # Pagination row (if needed)
    nav_row = []
    total_pages = (total + per_page - 1) // per_page
    
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ السابق", callback_data=f"open:page:{parent_id if parent_id else 'root'}:{page-1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="ignore"))
    if (page + 1) * per_page < total:
        nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"open:page:{parent_id if parent_id else 'root'}:{page+1}"))
    
    if nav_row:
        buttons.append(nav_row)
    
    # Back buttons (always full width, 1 per row)
    if parent_id is not None:
        section = get_section(parent_id)
        if section and section["parent_id"] is not None:
            buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"open:{section['parent_id']}:0")])
        else:
            buttons.append([InlineKeyboardButton("⬅️ رجوع الى البداية", callback_data="open:root:0")])
    
    if not buttons:
        return None
    
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = build_keyboard(None, 0)
    
    user = update.effective_user
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
                   (user.id, user.username, user.first_name))
    conn.commit()
    conn.close()
    
    if keyboard:
        await update.message.reply_text(
            "📚 *مرحباً بك في بوت الموارد!*\n\nحدد شعبتك:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "📚 *مرحباً!*\n\nلا توجد موارد بعد.",
            parse_mode="Markdown"
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "ignore":
        return
    
    parts = data.split(":")
    
    # Handle pagination
    if len(parts) >= 4 and parts[1] == "page":
        parent_id = None if parts[2] == "root" else int(parts[2])
        page = int(parts[3])
        keyboard = build_keyboard(parent_id, page)
        section = get_section(parent_id) if parent_id else None
        
        if parent_id is None:
            text = "📚 *القائمة الرئيسية*\n\nحدد شعبتك:"
        else:
            text = f"📂 *{section['emoji']} {section['title']}*\n\nحدد عنصرا:"
        
        if keyboard:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await query.edit_message_text(text=f"{text}\n\n_مجلد فارغ._", parse_mode="Markdown")
        return
    
    # Normal navigation
    section_id = None if parts[1] == "root" else int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    section = get_section(section_id) if section_id else None
    
    # Folder: show children
    if section is None or section["type"] == "folder":
        keyboard = build_keyboard(section_id, page)
        
        if section is None:
            text = "📚 *القائمة الرئيسية*\n\nحدد شعبتك:"
        else:
            text = f"📂 *{section['emoji']} {section['title']}*\n\nحدد عنصرا:"
        
        if keyboard:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            parent_kb = build_keyboard(section["parent_id"] if section else None, 0)
            await query.edit_message_text(text=f"{text}\n\n_مجلد فارغ._", reply_markup=parent_kb, parse_mode="Markdown")
        return
    
    # Text: show content
    if section["type"] == "text":
        content = section["content"] or "_لا يوجد محتوى_"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data=f"open:{section['parent_id']}:0")]])
        
        if len(content) > 4000:
            chunks = [content[i:i+4000] for i in range(0, len(content), 4000)]
            await query.edit_message_text(
                text=f"📝 *{section['emoji']} {section['title']}*\n\n{chunks[0]}",
                reply_markup=keyboard, parse_mode="Markdown"
            )
            for chunk in chunks[1:]:
                await context.bot.send_message(chat_id=query.message.chat_id, text=chunk, parse_mode="Markdown")
        else:
            await query.edit_message_text(
                text=f"📝 *{section['emoji']} {section['title']}*\n\n{content}",
                reply_markup=keyboard, parse_mode="Markdown"
            )
        return
    
    # Link: show URL
    if section["type"] == "link":
        text = f"🔗 *{section['emoji']} {section['title']}*\n\n{section['content']}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data=f"open:{section['parent_id']}:0")]])
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=False)
        return
    
    # File: send file
    if section["type"] == "file":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data=f"open:{section['parent_id']}:0")]])
        await query.edit_message_text(
            text=f"📄 *{section['emoji']} {section['title']}*\n\nجاري إرسال الملف...",
            reply_markup=keyboard, parse_mode="Markdown"
        )
        
        try:
            file_path = section["content"]
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=f,
                        caption=f"{section['emoji']} {section['title']}",
                        reply_markup=keyboard
                    )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="❌ الملف غير موجود على الخادم.",
                    reply_markup=keyboard
                )
        except Exception as e:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"❌ خطأ: {str(e)}",
                reply_markup=keyboard
            )
        return


def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 البوت يعمل! اضغط Ctrl+C للإيقاف.")
    application.run_polling()


if __name__ == "__main__":
    main()