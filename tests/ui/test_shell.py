from nicegui import ui


async def test_shell_shows_quota_and_links(user):
    await user.open("/")
    for text in ("Educational Agent", "Gemini:", "Library", "Progress", "How it works"):
        await user.should_see(text)


async def test_create_course_appears_in_selector(user, services):
    await user.open("/")
    user.find("New course").click()
    user.find(kind=ui.input, marker="course-name").type("Statistics")
    user.find("Create").click()
    assert [c.name for c in services.courses.list_courses()] == ["Statistics"]
    await user.open("/")
    await user.should_see("Statistics")
    selects = user.find(kind=ui.select).elements
    assert selects and all("Statistics" in s.options.values() for s in selects)


async def test_course_map_shows_shared_topic_twice(user, services):
    course = services.courses.create_course("ML")
    m1, m2 = services.courses.add_module(course.id, "Module 1"), services.courses.add_module(course.id, "Module 2")
    topic = services.courses.add_topic(course.id, "Shared topic")
    services.courses.link_topic(m1, topic)
    services.courses.link_topic(m2, topic)
    await user.open("/")
    await user.should_see("Module 1")
    await user.should_see("Module 2")
    assert len(user.find("Shared topic").elements) == 2


async def test_send_shows_labelled_reply(user):
    await user.open("/")
    user.find(kind=ui.textarea).type("hello")
    user.find("Send").click()
    await user.should_see("Analytics")
    await user.should_see("echo: hello")


async def test_placeholder_page(user):
    await user.open("/notes")
    await user.should_see("Coming in Plan 3")


async def test_ask_another_agent(user, services):
    await user.open("/")
    user.find(kind=ui.textarea).type("hello")
    user.find("Send").click()
    await user.should_see("Ask instead:")
    for name in ("Tutor", "Notes maker", "Coding"):
        await user.should_see(name)
    assert "Analytics" not in [b.text for b in user.find(kind=ui.button).elements]
    user.find(kind=ui.button, content="Coding").click()
    await user.should_see("coding says hi")
    await user.should_see("@code hello")
    (thread_id, text, wrong, agent), = services.chat.resent
    assert (text, wrong.agent, agent) == ("hello", "analytics", "coding")


async def test_warnings_banner(tmp_path, make_user, build_services):
    msg = "Ollama isn't running. Start it with: ollama serve"
    async with make_user(build_services(tmp_path, [msg])) as user:
        await user.open("/")
        await user.should_see(msg)
        await user.should_see("Dismiss")
        user.find("Dismiss").click()
        await user.should_not_see(msg)


async def test_history_reload_shows_chip_but_no_buttons(user, services):
    thread = services.threads.create(None)
    services.chat.canned_history = [("user", "hi"), ("tutor", "hello there")]
    await user.open(f"/chat/{thread.id}")
    await user.should_see("Tutor")
    await user.should_see("hello there")
    await user.should_not_see("Ask instead:")


async def test_history_mermaid_labels_are_quoted_before_render(user, services):
    thread = services.threads.create(None)
    block = "```mermaid\ngraph TD\n  A[Start] --> B[Loss (error)]\n```"
    services.chat.canned_history = [("user", "hi"), ("tutor", block)]
    await user.open(f"/chat/{thread.id}")
    await user.should_see('B["Loss (error)"]')
