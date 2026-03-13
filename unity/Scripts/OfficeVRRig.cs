/*
 * NIGHTMARE ENGINE — OfficeVRRig.cs
 *
 * Manages the VR player's constraints and look mechanics in the office.
 * - Locks teleportation to the office chair/desk area only
 * - Detects when the player is looking at the left/right door window
 *   (triggers the light-check visual when light is on)
 * - Plays the ambient office audio (fans, distant sounds)
 *
 * Setup:
 *  1. Attach to the XR Rig GameObject
 *  2. Assign MainCamera (Camera under XR Rig)
 *  3. Assign LeftWindowTrigger, RightWindowTrigger (small colliders on door windows)
 *  4. Assign the two DoorLightControllers
 *  5. Optionally assign AmbientSource for looping office background audio
 */

using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;

public class OfficeVRRig : MonoBehaviour
{
    [Header("Camera")]
    public Camera MainCamera;

    [Header("Door Window Triggers")]
    [Tooltip("Small BoxCollider trigger in front of the left door window.")]
    public Collider LeftWindowTrigger;
    [Tooltip("Small BoxCollider trigger in front of the right door window.")]
    public Collider RightWindowTrigger;

    [Header("Door Controllers")]
    public DoorLightController LeftDoorCtrl;
    public DoorLightController RightDoorCtrl;

    [Header("Window Peek Overlays")]
    [Tooltip("Canvas/image that shows hallway through left window when light is on.")]
    public GameObject LeftWindowView;
    public GameObject RightWindowView;

    [Header("Audio")]
    public AudioSource AmbientSource;
    public AudioClip OfficeAmbientLoop;   // fan hum, distant music

    [Header("Locomotion Constraint")]
    [Tooltip("Keep the player inside this radius from the office anchor.")]
    public Transform OfficeAnchor;
    public float MaxOfficeRadius = 0.8f;

    // ── Private ───────────────────────────────────────────────────────────────

    private CharacterController _characterController;

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    private void Start()
    {
        _characterController = GetComponent<CharacterController>();

        // Start ambient audio
        if (AmbientSource != null && OfficeAmbientLoop != null)
        {
            AmbientSource.clip = OfficeAmbientLoop;
            AmbientSource.loop = true;
            AmbientSource.volume = 0.4f;
            AmbientSource.Play();
        }

        if (LeftWindowView  != null) LeftWindowView.SetActive(false);
        if (RightWindowView != null) RightWindowView.SetActive(false);
    }

    private void Update()
    {
        ConstrainToOffice();
        CheckWindowLook();
    }

    // ── Office Constraint ─────────────────────────────────────────────────────

    private void ConstrainToOffice()
    {
        if (OfficeAnchor == null) return;

        Vector3 playerPos  = transform.position;
        Vector3 anchorPos  = OfficeAnchor.position;
        Vector2 diff       = new Vector2(playerPos.x - anchorPos.x, playerPos.z - anchorPos.z);

        if (diff.magnitude > MaxOfficeRadius)
        {
            diff = diff.normalized * MaxOfficeRadius;
            transform.position = new Vector3(
                anchorPos.x + diff.x,
                playerPos.y,
                anchorPos.z + diff.y
            );
        }
    }

    // ── Window Look Detection ─────────────────────────────────────────────────

    private void CheckWindowLook()
    {
        if (MainCamera == null) return;

        Ray ray = new Ray(MainCamera.transform.position, MainCamera.transform.forward);

        bool lookingLeft  = LeftWindowTrigger  != null &&
                            LeftWindowTrigger.bounds.IntersectRay(ray);
        bool lookingRight = RightWindowTrigger != null &&
                            RightWindowTrigger.bounds.IntersectRay(ray);

        // Show window view only when light is on and player is looking at window
        if (LeftWindowView != null)
        {
            bool showLeft = lookingLeft && LeftDoorCtrl != null;
            LeftWindowView.SetActive(showLeft);
        }

        if (RightWindowView != null)
        {
            bool showRight = lookingRight && RightDoorCtrl != null;
            RightWindowView.SetActive(showRight);
        }
    }
}
