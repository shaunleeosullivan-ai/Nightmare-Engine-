/*
 * NIGHTMARE ENGINE — AnimatronicAvatarController.cs
 *
 * Controls the visual and audio presence of a single animatronic.
 * - Shows/hides the mesh based on room visibility
 * - Plays idle vs "at door" animation
 * - Handles Foxy's charge run
 *
 * Setup:
 *  1. Create a prefab for each animatronic (Freddy, Bonnie, Chica, Foxy)
 *  2. Attach this script to each prefab root
 *  3. Assign Animator, AudioSource, and room anchor transforms
 *  4. Room anchors are empty GameObjects placed at each room's spawn point
 *     Name them exactly matching the room IDs (e.g. "show_stage", "west_hall_corner")
 *
 * Room anchors you need in the scene:
 *   show_stage, dining_area, backstage, supply_closet,
 *   west_hall, west_hall_corner, pirate_cove,
 *   restrooms, kitchen, east_hall, east_hall_corner
 */

using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class AnimatronicAvatarController : MonoBehaviour
{
    [Header("Identity")]
    public string AnimatronicName;   // "freddy" | "bonnie" | "chica" | "foxy"

    [Header("Components")]
    public Animator Anim;
    public AudioSource AudioSrc;

    [Header("Audio Clips")]
    public AudioClip MovementSound;
    public AudioClip AtDoorSound;   // breathing / tapping at door
    public AudioClip ChargeSound;   // Foxy sprint

    [Header("Room Anchors")]
    [Tooltip("Drag the parent Transform that contains all room anchor GameObjects (named by room ID).")]
    public Transform RoomAnchorParent;

    // Rooms that the player can see directly via camera — animatronic is visible here.
    // The Office itself has no camera and the animatronic at the door is seen through the window.
    private static readonly HashSet<string> CameraVisibleRooms = new()
    {
        "show_stage", "dining_area", "backstage", "supply_closet",
        "west_hall", "west_hall_corner", "pirate_cove",
        "restrooms", "east_hall", "east_hall_corner"
        // "kitchen" intentionally omitted (blind spot)
    };

    // Rooms that are visible through door windows (player physically looks left/right)
    private static readonly HashSet<string> DoorWindowRooms = new()
    {
        "west_hall_corner", "east_hall_corner"
    };

    // ── Animator parameter hashes ─────────────────────────────────────────────

    private static readonly int AnimIdle    = Animator.StringToHash("Idle");
    private static readonly int AnimAtDoor  = Animator.StringToHash("AtDoor");
    private static readonly int AnimCharge  = Animator.StringToHash("Charge");
    private static readonly int AnimJumpscare = Animator.StringToHash("Jumpscare");

    // ── State ─────────────────────────────────────────────────────────────────

    private string _currentRoom = "";
    private bool _atDoor = false;
    private MeshRenderer[] _renderers;

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    private void Awake()
    {
        _renderers = GetComponentsInChildren<MeshRenderer>();
        SetVisible(false);

        // Subscribe to Foxy-specific events
        if (AnimatronicName == "foxy")
        {
            FnafWebSocketClient.OnFoxyStageChange += HandleFoxyStage;
            FnafWebSocketClient.OnFoxyCharging    += HandleFoxyCharge;
        }
    }

    private void OnDestroy()
    {
        if (AnimatronicName == "foxy")
        {
            FnafWebSocketClient.OnFoxyStageChange -= HandleFoxyStage;
            FnafWebSocketClient.OnFoxyCharging    -= HandleFoxyCharge;
        }
    }

    // ── Public API ────────────────────────────────────────────────────────────

    public void MoveTo(string roomId, bool atDoor)
    {
        _currentRoom = roomId;
        _atDoor = atDoor;

        // Snap to anchor
        Transform anchor = FindAnchor(roomId);
        if (anchor != null)
        {
            transform.position = anchor.position;
            transform.rotation = anchor.rotation;
        }

        // Show only in camera-visible rooms or door windows
        bool visible = CameraVisibleRooms.Contains(roomId);
        SetVisible(visible);

        // Animation state
        if (Anim != null)
        {
            Anim.SetBool(AnimAtDoor, atDoor);
            Anim.SetBool(AnimIdle, !atDoor);
        }

        // Audio feedback
        if (AudioSrc != null)
        {
            AudioClip clip = atDoor ? AtDoorSound : MovementSound;
            if (clip != null)
            {
                AudioSrc.clip = clip;
                AudioSrc.Play();
            }
        }
    }

    public void PlayJumpscare()
    {
        SetVisible(true);
        Anim?.SetTrigger(AnimJumpscare);
    }

    // ── Foxy ──────────────────────────────────────────────────────────────────

    private void HandleFoxyStage(int stage)
    {
        // Foxy's curtain state on the camera feed (stage 0-3)
        // Visual handled by the CameraMonitor texture swap — nothing to do here
        // unless you have a Foxy-specific curtain mesh in the scene
        Debug.Log($"[Foxy] Stage {stage}");
    }

    private void HandleFoxyCharge()
    {
        if (AnimatronicName != "foxy") return;
        SetVisible(true);
        Anim?.SetTrigger(AnimCharge);
        if (AudioSrc != null && ChargeSound != null)
        {
            AudioSrc.clip = ChargeSound;
            AudioSrc.Play();
        }
        // Start Coroutine to move Foxy to west_hall then west_hall_corner
        StartCoroutine(FoxyChargeCoroutine());
    }

    private IEnumerator FoxyChargeCoroutine()
    {
        MoveTo("west_hall", false);
        yield return new WaitForSeconds(1.5f);
        MoveTo("west_hall_corner", true);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private void SetVisible(bool visible)
    {
        foreach (var r in _renderers)
            r.enabled = visible;
    }

    private Transform FindAnchor(string roomId)
    {
        if (RoomAnchorParent == null) return null;
        return RoomAnchorParent.Find(roomId);
    }
}
