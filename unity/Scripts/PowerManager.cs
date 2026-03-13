/*
 * NIGHTMARE ENGINE — PowerManager.cs
 *
 * Drives the power bar UI and environmental lighting.
 * - Updates the power bar fill and colour
 * - Flickers lights at low power
 * - Cuts all lights on power out
 *
 * Setup:
 *  1. Attach to a persistent UI GameObject
 *  2. Assign PowerFill (Image), PowerLabel (TMP), OfficeLights array
 */

using System.Collections;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class PowerManager : MonoBehaviour
{
    [Header("UI")]
    public Image PowerFill;
    public TextMeshProUGUI PowerLabel;

    [Header("Office Lights")]
    [Tooltip("All light sources in the office that should flicker/cut on power loss.")]
    public Light[] OfficeLights;

    [Header("Colours")]
    public Color HighPowerColor  = new Color(0.0f, 0.8f, 0.0f);
    public Color MidPowerColor   = new Color(0.9f, 0.7f, 0.0f);
    public Color LowPowerColor   = new Color(0.9f, 0.1f, 0.1f);

    // ── State ─────────────────────────────────────────────────────────────────

    private float _currentPower = 100f;
    private bool _powerOut = false;
    private Coroutine _flickerCoroutine;

    // ── Public API ────────────────────────────────────────────────────────────

    public void UpdatePower(float power)
    {
        if (_powerOut) return;
        _currentPower = power;

        float fraction = Mathf.Clamp01(power / 100f);

        // Fill bar
        if (PowerFill != null)
        {
            PowerFill.fillAmount = fraction;
            PowerFill.color = power > 60f ? HighPowerColor
                            : power > 25f ? MidPowerColor
                            : LowPowerColor;
        }

        // Label
        if (PowerLabel != null)
            PowerLabel.text = $"Power: {Mathf.RoundToInt(power)}%";

        // Flicker at low power
        if (power <= 15f && _flickerCoroutine == null)
            _flickerCoroutine = StartCoroutine(FlickerLights());
        else if (power > 15f && _flickerCoroutine != null)
        {
            StopCoroutine(_flickerCoroutine);
            _flickerCoroutine = null;
            SetLightsOn(true);
        }
    }

    public void TriggerPowerOut()
    {
        _powerOut = true;
        if (_flickerCoroutine != null)
        {
            StopCoroutine(_flickerCoroutine);
            _flickerCoroutine = null;
        }
        SetLightsOn(false);

        if (PowerLabel != null)  PowerLabel.text = "Power: 0%";
        if (PowerFill  != null)  PowerFill.fillAmount = 0f;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private void SetLightsOn(bool on)
    {
        foreach (var l in OfficeLights)
            if (l != null) l.enabled = on;
    }

    private IEnumerator FlickerLights()
    {
        while (true)
        {
            SetLightsOn(false);
            yield return new WaitForSeconds(Random.Range(0.05f, 0.15f));
            SetLightsOn(true);
            yield return new WaitForSeconds(Random.Range(0.1f, 0.4f));
        }
    }
}
