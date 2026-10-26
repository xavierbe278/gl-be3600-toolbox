# GLANIM_SWITCH_HOOK
# Repurpose the OEM physical switch: ON = third-party glanim, OFF = OEM gl_screen.
if [ -x /usr/bin/glanim-switch ]; then
    /usr/bin/glanim-switch "$ACTION"
    exit 0
fi
# GLANIM_SWITCH_HOOK_END
