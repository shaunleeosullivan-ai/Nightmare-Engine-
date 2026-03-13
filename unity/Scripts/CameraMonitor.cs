/*
 * NIGHTMARE ENGINE — CameraMonitor.cs
 *
 * The security camera tablet the player holds in VR.
 * - Grab/ungrab sends camera_open / camera_close to server
 * - Buttons on the tablet switch between camera feeds
 * - Each feed is a RenderTexture from a Camera placed in that room
 * - Animatronic icons overlay on feeds when an animatronic is present
 * - Checking cam1C (Pirate Cove) is tracked specifically for Foxy's AI
 *
 * Setup:
 *  1. Create a world-space Canvas attached to a tablet mesh
 *  2. Assign FeedDisplay (RawImage), CameraButtons, RoomCameras dict
 *  3. Place Camera components at each room anchor — assign their RenderTextures here
 *  4. Attach XRGrabInteractable to the tablet mesh for VR grab
 *
 * Camera IDs (match server): cam1A, cam1B, cam1C, cam2A, cam2B, cam3, cam4A, cam4B, cam5
 */

using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using UnityEngine.XR.Interaction.Toolkit;

public class CameraMonitor : MonoBehaviour
{
    [Header("UI")]
    public RawImage FeedDisplay;
    public TextMeshProUGUI CameraLabel;

    [Header("Camera Feeds")]
    [Tooltip("Map from camera_id (e.g. 'cam1A') to the RenderTexture of that room's Camera.")]
    public CameraFeedEntry[] CameraFeeds;

    [Header("Animatronic Icons")]
    [Tooltip("Small icons shown on feed when an animatronic is in that room.")]
    public AnimatronicIconEntry[] AnimatronicIcons;

    [Header("Static (noise) texture shown when camera has no feed")]
    public Texture2D StaticTexture;

    [Header("Foxy special cam")]
    [Tooltip("Foxy curtain textures indexed by stage 0-3.")]
    public Texture2D[] FoxyCurtainTextures;

    // ── Private ───────────────────────────────────────────────────────────────

    private Dictionary<string, RenderTexture> _feedMap = new();
    private Dictionary<string, GameObject>    _iconMap = new();
    private string _activeCamId = "cam1A";
    private bool   _isOpen = false;
    private FnafWebSocketClient _ws;

    // Which camera_id maps to which animatronic room (from server /api/v1/fnaf/rooms)
    private static readonly Dictionary<string, string> CamToRoom = new()
    {
        { "cam1A", "show_stage"       },
        { "cam1B", "dining_area"      },
        { "cam1C", "pirate_cove"      },
        { "cam2A", "west_hall"        },
        { "cam2B", "west_hall_corner" },
        { "cam3",  "east_hall"        },
        { "cam4A", "east_hall_corner" },
        { "cam4B", "restrooms"        },
        { "cam5",  "backstage"        },
    };

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    private void Awake()
    {
        _ws = FindObjectOfType<FnafWebSocketClient>();

        foreach (var entry in CameraFeeds)
            _feedMap[entry.CamId] = entry.Texture;

        foreach (var entry in AnimatronicIcons)
        {
            _iconMap[entry.AnimatronicName] = entry.IconObject;
            entry.IconObject.SetActive(false);
        }
    }

    private void OnEnable()
    {
        FnafWebSocketClient.OnStateTick += HandleStateTick;
        FnafWebSocketClient.OnFoxyStageChange += HandleFoxyStage;
    }

    private void OnDisable()
    {
        FnafWebSocketClient.OnStateTick -= HandleStateTick;
        FnafWebSocketClient.OnFoxyStageChange -= HandleFoxyStage;
    }

    // ── XR Grab events (wire these from XRGrabInteractable in Inspector) ──────

    public void OnGrab()
    {
        _isOpen = true;
        _ws?.OpenCameraMonitor();
        SwitchTo(_activeCamId);
    }

    public void OnRelease()
    {
        _isOpen = false;
        _ws?.CloseCameraMonitor();
        HideAllIcons();
    }

    // ── Camera buttons (wire from UI Buttons in Inspector) ───────────────────

    public void SwitchTo(string camId)
    {
        _activeCamId = camId;

        if (_feedMap.TryGetValue(camId, out RenderTexture rt))
            FeedDisplay.texture = rt;
        else
            FeedDisplay.texture = StaticTexture;

        if (CameraLabel != null)
            CameraLabel.text = $"CAM {camId.ToUpper()}";

        if (camId == "cam1C")
            _ws?.CheckPirateCove();
        else
            _ws?.SwitchCamera(camId);
    }

    // ── State tick — update icon overlay ─────────────────────────────────────

    private void HandleStateTick(StateTick tick)
    {
        if (!_isOpen || tick.animatronic_positions == null) return;

        string currentRoom = CamToRoom.GetValueOrDefault(_activeCamId, "");

        foreach (var kvp in tick.animatronic_positions)
        {
            string animName = kvp.Key;
            string room     = kvp.Value;
            bool visible    = (room == currentRoom) && _isOpen;

            if (_iconMap.TryGetValue(animName, out GameObject icon))
                icon.SetActive(visible);
        }
    }

    private void HandleFoxyStage(int stage)
    {
        // If player is currently watching cam1C, update the curtain texture
        if (_activeCamId != "cam1C") return;
        if (FoxyCurtainTextures == null || stage >= FoxyCurtainTextures.Length) return;
        FeedDisplay.texture = FoxyCurtainTextures[stage];
    }

    private void HideAllIcons()
    {
        foreach (var icon in _iconMap.Values)
            icon.SetActive(false);
    }
}

// ── Inspector-friendly entry types ────────────────────────────────────────────

[System.Serializable]
public class CameraFeedEntry
{
    public string        CamId;
    public RenderTexture Texture;
}

[System.Serializable]
public class AnimatronicIconEntry
{
    public string     AnimatronicName;
    public GameObject IconObject;
}
