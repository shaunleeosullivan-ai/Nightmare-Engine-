/*
 * NIGHTMARE ENGINE — FnafWebSocketClient.cs
 *
 * Manages the WebSocket connection to the Python backend.
 * Parses incoming JSON by "type" field and fires C# events.
 * Sends player actions as JSON strings.
 *
 * Setup:
 *  1. Install NativeWebSocket: https://github.com/endel/NativeWebSocket
 *     (Unity Package Manager → Add package from git URL)
 *     com.endel.nativewebsocket
 *  2. Attach this script to a persistent GameObject (e.g. "NetworkManager")
 *  3. Set ServerUrl and ExpId in the Inspector (or call Connect() at runtime)
 *
 * Dependencies: NativeWebSocket, Newtonsoft.Json (included in Unity 2021+)
 */

using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using NativeWebSocket;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

public class FnafWebSocketClient : MonoBehaviour
{
    [Header("Connection")]
    [Tooltip("e.g. ws://192.168.1.100:8000")]
    public string ServerUrl = "ws://localhost:8000";
    public string ExpId = "";

    // ── Events ────────────────────────────────────────────────────────────────

    public static event Action<StateTick>      OnStateTick;
    public static event Action<AnimMoved>      OnAnimMoved;
    public static event Action<JumpscareData>  OnJumpscare;
    public static event Action                 OnPowerOut;
    public static event Action<NightComplete>  OnNightComplete;
    public static event Action<int>            OnFoxyStageChange;
    public static event Action                 OnFoxyCharging;
    public static event Action<float>          OnFoxyBlocked;     // power remaining
    public static event Action<string, bool>   OnDoorState;       // side, closed
    public static event Action<string, bool>   OnLightState;      // side, on
    public static event Action<bool>           OnConnected;

    // ── Internal ──────────────────────────────────────────────────────────────

    private WebSocket _ws;
    private bool _isConnecting = false;

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    private void Start()
    {
        if (!string.IsNullOrEmpty(ExpId))
            Connect(ExpId);
    }

    private void Update()
    {
#if !UNITY_WEBGL || UNITY_EDITOR
        _ws?.DispatchMessageQueue();
#endif
    }

    private void OnDestroy()
    {
        _ws?.Close();
    }

    // ── Public API ────────────────────────────────────────────────────────────

    public async void Connect(string expId)
    {
        if (_isConnecting) return;
        _isConnecting = true;
        ExpId = expId;

        string url = $"{ServerUrl}/ws/session/{expId}";
        _ws = new WebSocket(url);

        _ws.OnOpen    += HandleOpen;
        _ws.OnMessage += HandleMessage;
        _ws.OnError   += HandleError;
        _ws.OnClose   += HandleClose;

        await _ws.Connect();
    }

    public void SendAction(object actionObj)
    {
        if (_ws?.State == WebSocketState.Open)
        {
            string json = JsonConvert.SerializeObject(actionObj);
            _ws.SendText(json);
        }
        else
        {
            Debug.LogWarning("[FNAF WS] Cannot send — not connected.");
        }
    }

    // Convenience helpers
    public void ToggleDoor(string side) =>
        SendAction(new { action = "toggle_door", side });

    public void ToggleLight(string side) =>
        SendAction(new { action = "toggle_light", side });

    public void OpenCameraMonitor() =>
        SendAction(new { action = "camera_open" });

    public void CloseCameraMonitor() =>
        SendAction(new { action = "camera_close" });

    public void SwitchCamera(string camId) =>
        SendAction(new { action = "switch_camera", cam_id = camId });

    public void CheckPirateCove() =>
        SendAction(new { action = "check_pirate_cove" });

    // ── Handlers ──────────────────────────────────────────────────────────────

    private void HandleOpen()
    {
        _isConnecting = false;
        Debug.Log("[FNAF WS] Connected.");
        OnConnected?.Invoke(true);
    }

    private void HandleMessage(byte[] bytes)
    {
        string json = Encoding.UTF8.GetString(bytes);
        try
        {
            JObject obj = JObject.Parse(json);
            string type = obj["type"]?.ToString();

            switch (type)
            {
                case "state_tick":
                    OnStateTick?.Invoke(obj.ToObject<StateTick>());
                    break;
                case "anim_moved":
                    OnAnimMoved?.Invoke(obj.ToObject<AnimMoved>());
                    break;
                case "jumpscare":
                    OnJumpscare?.Invoke(obj.ToObject<JumpscareData>());
                    break;
                case "power_out":
                    OnPowerOut?.Invoke();
                    break;
                case "night_complete":
                    OnNightComplete?.Invoke(obj.ToObject<NightComplete>());
                    break;
                case "foxy_stage_change":
                    OnFoxyStageChange?.Invoke(obj["stage"]?.Value<int>() ?? 0);
                    break;
                case "foxy_charging":
                    OnFoxyCharging?.Invoke();
                    break;
                case "foxy_blocked":
                    OnFoxyBlocked?.Invoke(obj["power_remaining"]?.Value<float>() ?? 0f);
                    break;
                case "door_state":
                    OnDoorState?.Invoke(
                        obj["side"]?.ToString(),
                        obj["closed"]?.Value<bool>() ?? false
                    );
                    break;
                case "light_state":
                    OnLightState?.Invoke(
                        obj["side"]?.ToString(),
                        obj["on"]?.Value<bool>() ?? false
                    );
                    break;
                default:
                    // Initial connection message or unknown — log only in editor
                    Debug.Log($"[FNAF WS] Unhandled message type: {type ?? "(null)"}\n{json}");
                    break;
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"[FNAF WS] JSON parse error: {ex.Message}\n{json}");
        }
    }

    private void HandleError(string error)
    {
        Debug.LogError($"[FNAF WS] Error: {error}");
        StartCoroutine(ReconnectAfterDelay(3f));
    }

    private void HandleClose(WebSocketCloseCode code)
    {
        Debug.Log($"[FNAF WS] Closed — code {code}");
        OnConnected?.Invoke(false);
        _isConnecting = false;
    }

    private IEnumerator ReconnectAfterDelay(float delay)
    {
        yield return new WaitForSeconds(delay);
        Connect(ExpId);
    }
}

// ── Data classes (match Python server JSON) ────────────────────────────────────

[Serializable]
public class StateTick
{
    public string type;
    public string phase;
    public float power;
    public float time_elapsed;
    public float time_remaining;
    public int hour;
    public bool door_left;
    public bool door_right;
    public bool light_left;
    public bool light_right;
    public bool camera_monitor_open;
    public string active_camera;
    public Dictionary<string, string> animatronic_positions;
    public Dictionary<string, bool>   at_doors;
    public int foxy_stage;
}

[Serializable]
public class AnimMoved
{
    public string type;
    public string animatronic;
    public string from_room;
    public string to_room;
    public bool at_door;
}

[Serializable]
public class JumpscareData
{
    public string type;
    public string animatronic;
    public string cause;
}

[Serializable]
public class NightComplete
{
    public string type;
    public int night;
    public float power_remaining;
}
