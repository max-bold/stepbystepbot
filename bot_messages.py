not_registered = [
    "Не вижу вашего ID в базе данных. Пожалуйста, отправьте команду /start чтобы зарегистрироваться.",
    "User {id} tried to get step but is not registered",
]
not_payed = [
    "У вас нет доступа к боту. Пожалуйста, отправьте команду /start чтобы получить ссылку на оплату.",
    "User {id} tried to get step but has not paid",
]
step_sent = [
    "Следующий урок пока недоступен. Пожалуйста, подождите. Вам придет напоминание",
    "User {id} requested next step, but step already sent",
]
script_completed = [
    "Вы успешно прошли весь курс! Поздравляем!",
    "User {id} has completed the script",
]
step_invite = [
    "Вам доступен следующий урок: {title}!\n\n{description}",
    "Sent next step invite to user {id}",
]

massage_failed = "Failed to send message to user {id}: {e}"

next_step_button = "Получить следующий урок"

on_message = [
    "К сожалению, этот бот не умеет отвечать на сообщения. Если у вас возникли проблемы, напишите {support_contact}.",
    "Received message from user {id}: {text}"
]
