const pressed = new Set();

document.addEventListener("keydown", (e) => {
    const key = e.key.toLowerCase();
    if ("wasd".includes(key) && !pressed.has(key)) {
        pressed.add(key);
        fetch("/command", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ key }),
        });
    }
});

document.addEventListener("keyup", (e) => {
    const key = e.key.toLowerCase();
    if (pressed.has(key)) {
        pressed.delete(key);
        if (pressed.size === 0) {
            fetch("/command", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ key: "stop" }),
            });
        }
    }
});
