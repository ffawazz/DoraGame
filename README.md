# Dora Dash!

A Pepsi Man-style 3D runner starring Dora (fan prototype). See `GDD.md` for the design.

## Play (Python, any PC)

```
pip install -r requirements.txt
python dora_dash.py
```

Controls: **A/D** or **←/→** lanes · **W/↑/Space** jump · **S/↓** slide · **P** pause · **Esc** back · **F11** toggle fullscreen (starts fullscreen; set `DORA_WINDOWED=1` to start windowed).
At the end of a level Dora says "I'm Dora the Explorer!" out loud using your OS voice.

Three levels (press 1, 2 or 3): Spooky Forest, Chaotic Highway, Crocodile Lake.
Reach the Banana Swing at the end of each one. Graphics and sound are generated in code, so no asset files are needed.

## Unity version

`Assets/Scripts/*.cs` is an alternative Unity prototype of the same game (see `GDD.md`).
