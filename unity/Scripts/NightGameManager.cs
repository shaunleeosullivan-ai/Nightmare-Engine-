/*
 * NIGHTMARE ENGINE — NightGameManager.cs
 *
 * Central coordinator for a FNAF night.
 * - Receives all WebSocket events from FnafWebSocketClient
 * - Maintains local mirror of game state
 * - Routes anim_moved events to AnimatronicAvatarControllers
 * - Triggers JumpscareController on game over
 * - Calls POST /api/v1/fnaf/start_night to begin
 *
 * Setup:
 *  1. Create a GameObject "NightGameManager" in your scene
 *  2. Assign all serialised references in Inspector
 *  3. Scene must also have a FnafWebSocketClient on another object
 *  4. Call StartNight() from your UI button
 */

using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using TMPro;

public class NightGameManager : MonoBehaviour
{
    // ── Inspector References ──────────────────────────────────────────────────

    [Header("Game Setup")]
    public FnafWebSocketClient wsClient;
    public int NightNumber = 1;
    public string ExpId = "";         // set before StartNight()
    public string BackendUrl = "http://localhost:8000";

    [Header("Animatronics")]
    public AnimatronicAvatarController FreddyController;
    public AnimatronicAvatarController BonnieController;
    public AnimatronicAvatarController ChicaController;
    public AnimatronicAvatarController FoxyController;

    [Header("Systems")]
    public JumpscareController JumpscareCtrl;
    public PowerManager PowerMgr;
    public CameraMonitor CamMonitor;

    [Header("UI")]
    public TextMeshProUGUI HourLabel;
    public TextMeshProUGUI PhaseLabel;
    public GameObject GameOverPanel;
    public GameObject SurvivedPanel;

    // ── State ─────────────────────────────────────────────────────────────────

    public string CurrentPhase { get; private set; } = "waiting";
    public Dictionary<string, string> AnimatronicPositions { get; private set; }
        = new Dictionary<string, string>();

    private static readonly Dictionary<string, string> HourLabels = new()
    {
        { "12", "12 AM" }, { "1", "1 AM" }, { "2", "2 AM" },
        { "3", "3 AM" },   { "4", "4 AM" }, { "5", "5 AM" }, { "6", "6 AM" },
    };

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    private void OnEnable()
    {
        FnafWebSocketClient.OnStateTick     += HandleStateTick;
        FnafWebSocketClient.OnAnimMoved     += HandleAnimMoved;
        FnafWebSocketClient.OnJumpscare     += HandleJumpscare;
        FnafWebSocketClient.OnPowerOut      += HandlePowerOut;
        FnafWebSocketClient.OnNightComplete += HandleNightComplete;
    }

    private void OnDisable()
    {
        FnafWebSocketClient.OnStateTick     -= HandleStateTick;
        FnafWebSocketClient.OnAnimMoved     -= HandleAnimMoved;
        FnafWebSocketClient.OnJumpscare     -= HandleJumpscare;
        FnafWebSocketClient.OnPowerOut      -= HandlePowerOut;
        FnafWebSocketClient.OnNightComplete -= HandleNightComplete;
    }

    // ── Public API ────────────────────────────────────────────────────────────

    public void StartNight()
    {
        StartCoroutine(StartNightCoroutine());
    }

    private IEnumerator StartNightCoroutine()
    {
        string url = $"{BackendUrl}/api/v1/fnaf/start_night";
        string body = JsonUtility.ToJson(new StartNightPayload
        {
            exp_id = ExpId,
            night_number = NightNumber,
        });

        using var req = new UnityEngine.Networking.UnityWebRequest(url, "POST");
        byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(body);
        req.uploadHandler   = new UnityEngine.Networking.UploadHandlerRaw(bodyRaw);
        req.downloadHandler = new UnityEngine.Networking.DownloadHandlerBuffer();
        req.SetRequestHeader("Content-Type", "application/json");

        yield return req.SendWebRequest();

        if (req.result != UnityEngine.Networking.UnityWebRequest.Result.Success)
        {
            Debug.LogError($"[FNAF] start_night failed: {req.error}");
        }
        else
        {
            Debug.Log($"[FNAF] Night {NightNumber} started — {req.downloadHandler.text}");
            wsClient.Connect(ExpId);
        }
    }

    // ── Event handlers ────────────────────────────────────────────────────────

    private void HandleStateTick(StateTick tick)
    {
        CurrentPhase = tick.phase;
        AnimatronicPositions = tick.animatronic_positions ?? AnimatronicPositions;

        // Update hour label
        if (HourLabel != null)
            HourLabel.text = HourLabels.GetValueOrDefault(tick.hour.ToString(), $"{tick.hour} AM");

        // Push to sub-systems
        PowerMgr?.UpdatePower(tick.power);
    }

    private void HandleAnimMoved(AnimMoved ev)
    {
        Debug.Log($"[FNAF] {ev.animatronic} moved: {ev.from_room} → {ev.to_room} (at_door:{ev.at_door})");

        AnimatronicAvatarController ctrl = ev.animatronic switch
        {
            "freddy" => FreddyController,
            "bonnie" => BonnieController,
            "chica"  => ChicaController,
            "foxy"   => FoxyController,
            _        => null,
        };

        ctrl?.MoveTo(ev.to_room, ev.at_door);
        AnimatronicPositions[ev.animatronic] = ev.to_room;
    }

    private void HandleJumpscare(JumpscareData data)
    {
        Debug.Log($"[FNAF] JUMPSCARE — {data.animatronic} ({data.cause})");
        CurrentPhase = "game_over";
        JumpscareCtrl?.TriggerJumpscare(data.animatronic, data.cause);
    }

    private void HandlePowerOut()
    {
        Debug.Log("[FNAF] Power out!");
        PowerMgr?.TriggerPowerOut();
    }

    private void HandleNightComplete(NightComplete data)
    {
        Debug.Log($"[FNAF] Night {data.night} survived! Power left: {data.power_remaining}");
        CurrentPhase = "survived";
        if (SurvivedPanel != null) SurvivedPanel.SetActive(true);
    }

    // ── Serializable helper ────────────────────────────────────────────────────

    [System.Serializable]
    private class StartNightPayload
    {
        public string exp_id;
        public int night_number;
    }
}
