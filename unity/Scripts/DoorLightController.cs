/*
 * NIGHTMARE ENGINE — DoorLightController.cs
 *
 * Controls one door (left or right) and its peephole light.
 * - Toggle() is called by the XR button interactable in the scene
 * - Animates the door sliding closed/open
 * - Enables the hallway light RenderTexture camera when light is on
 * - Sends toggle_door / toggle_light actions to the server
 *
 * Setup:
 *  1. Attach one instance to the LeftDoor and one to the RightDoor
 *  2. Set Side to "left" or "right"
 *  3. Assign DoorMesh, DoorAnimator, HallwayLightCamera, LightButton mesh
 *  4. Wire XRSimpleInteractable.selectEntered on each button to ToggleDoor / ToggleLight
 */

using System.Collections;
using UnityEngine;

public class DoorLightController : MonoBehaviour
{
    [Header("Identity")]
    public string Side = "left";  // "left" | "right"

    [Header("Door")]
    public Animator DoorAnimator;
    public AudioClip DoorCloseClip;
    public AudioClip DoorOpenClip;

    [Header("Light")]
    public Camera HallwayCamera;        // Camera that renders the hallway view
    public RenderTexture HallwayRT;     // The RenderTexture it renders into
    public Light HallwaySpotLight;      // Small spot light illuminating the hall
    public AudioClip LightClickClip;

    // ── State ─────────────────────────────────────────────────────────────────

    private bool _doorClosed = false;
    private bool _lightOn    = false;
    private AudioSource _audio;
    private FnafWebSocketClient _ws;

    private static readonly int AnimDoorClosed = Animator.StringToHash("DoorClosed");

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    private void Awake()
    {
        _audio = GetComponent<AudioSource>();
        if (_audio == null) _audio = gameObject.AddComponent<AudioSource>();
        _ws = FindObjectOfType<FnafWebSocketClient>();

        // Disable hallway camera until light is on (saves performance)
        if (HallwayCamera != null) HallwayCamera.enabled = false;
        if (HallwaySpotLight != null) HallwaySpotLight.enabled = false;
    }

    private void OnEnable()
    {
        FnafWebSocketClient.OnDoorState  += HandleDoorState;
        FnafWebSocketClient.OnLightState += HandleLightState;
    }

    private void OnDisable()
    {
        FnafWebSocketClient.OnDoorState  -= HandleDoorState;
        FnafWebSocketClient.OnLightState -= HandleLightState;
    }

    // ── Public API (wire to XR buttons) ──────────────────────────────────────

    /// <summary>Called by the door button XR interactable.</summary>
    public void ToggleDoor()
    {
        _ws?.ToggleDoor(Side);
        // Optimistic local update (server confirms via OnDoorState event)
        ApplyDoorState(!_doorClosed);
        PlayClip(_doorClosed ? DoorCloseClip : DoorOpenClip);
    }

    /// <summary>Called by the light button XR interactable.</summary>
    public void ToggleLight()
    {
        _ws?.ToggleLight(Side);
        ApplyLightState(!_lightOn);
        PlayClip(LightClickClip);
    }

    // ── Server confirmation handlers ─────────────────────────────────────────

    private void HandleDoorState(string side, bool closed)
    {
        if (side != Side) return;
        ApplyDoorState(closed);
    }

    private void HandleLightState(string side, bool on)
    {
        if (side != Side) return;
        ApplyLightState(on);
    }

    // ── Visual application ────────────────────────────────────────────────────

    private void ApplyDoorState(bool closed)
    {
        _doorClosed = closed;
        DoorAnimator?.SetBool(AnimDoorClosed, closed);
    }

    private void ApplyLightState(bool on)
    {
        _lightOn = on;
        if (HallwayCamera    != null) HallwayCamera.enabled    = on;
        if (HallwaySpotLight != null) HallwaySpotLight.enabled = on;
    }

    private void PlayClip(AudioClip clip)
    {
        if (clip != null && _audio != null)
            _audio.PlayOneShot(clip);
    }
}
