import display  # Initializes the configured display, touch input, and task handler.
import lvgl as lv



current_backlight = display.get_backlight()


display.set_backlight(100)  # Set backlight to 100% for better visibility



click_count = 0


def on_button_clicked(event):
    global click_count
    click_count += 1
    button_label.set_text("Pressed %d" % click_count)
    print("Button pressed:", click_count)


screen = lv.screen_active()
screen.set_style_bg_color(lv.color_hex(0x18212B), 0)

heading = lv.label(screen)
heading.set_text("Waveshare ESP32-P4")
heading.align(lv.ALIGN.CENTER, 0, -90)

button = lv.button(screen)
button.set_size(220, 90)
button.align(lv.ALIGN.CENTER, 0, 20)
button.add_event_cb(on_button_clicked, lv.EVENT.CLICKED, None)

button_label = lv.label(button)
button_label.set_text("Press me")
button_label.center()

print("LVGL button example ready")
