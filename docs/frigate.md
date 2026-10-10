# Frigate on the Turing Pi cluster

## Purpose and boundary

Frigate is deployed as an experimental K3s workload on the Turing RK1 node `TR4`. Its intended role is local object detection and review/alert generation for the existing Reolink cameras.

UniFi Protect on `odin` remains the authoritative NVR and retains the full-quality camera recordings. Frigate is not intended to replace Protect or retain continuous, long-term video. Its media retention should remain limited to short clips associated with useful alerts.

## Confirmed deployment

| Item | Current value |
|---|---|
| Kubernetes namespace | `frigate` |
| Workload | Single Kubernetes Deployment pinned to `TR4` |
| Container image | `ghcr.io/blakeblackshear/frigate:stable-rk` |
| Node | `TR4` (`192.168.0.184`), Turing RK1 with RK3588 and 8 GB RAM |
| Boot OS | Ubuntu 22.04.5 LTS, Rockchip BSP kernel `5.10.160-rockchip` |
| Authenticated UI | HTTPS NodePort `30971` forwarding to container port `8971` |
| Direct UI | `https://192.168.0.184:30971` (self-signed certificate observed) |
| Internal API | Container port `5000`; unauthenticated and must not be exposed outside trusted cluster networking |
| Configuration storage | `/mnt/k3s-storage/frigate/config` on TR4, mounted at `/config` |
| Media storage | `/mnt/k3s-storage/frigate/media` on TR4 NVMe, mounted at `/media/frigate` |
| Temporary media | Memory-backed Kubernetes `emptyDir` mounts for `/tmp/cache` and `/dev/shm`, each limited to 512 MiB |
| Resource request | 500 millicores and 1 GiB RAM |
| Resource limit | 6 CPU and 6 GiB RAM |

The Deployment currently runs privileged so the Rockchip media and NPU devices can be used. The following host resources were passed through to the pod:

- `/dev/dri`
- `/dev/dma_heap`
- `/dev/rga`
- `/dev/mpp_service`
- `/sys`

The original manifest was applied from `/tmp/frigate.yaml` on the administering host. That temporary path is not an authoritative configuration source. A future maintenance task should capture the deployment, services, storage mounts, resource limits, and node selection in version-controlled manifests or a Helm values file.

## RK3588 acceleration

TR4 was confirmed to expose:

- `/dev/dri/card0` and `/dev/dri/card1`;
- `/dev/dri/renderD128` and `/dev/dri/renderD129`;
- `/dev/dma_heap`;
- `/dev/mpp_service`;
- `/dev/rga`;
- RKNPU driver `v0.9.2`, with three NPU cores visible.

FFmpeg hardware decoding uses the Frigate preset:

```yaml
ffmpeg:
  hwaccel_args: preset-rkmpp
```

The literal UI description `Rockchip RKMPP` must not be placed in `hwaccel_args`. Doing so previously caused FFmpeg to treat `Rockchip` as an output filename and terminate with an output-format/muxer error.

The confirmed detector configuration is:

```yaml
detectors:
  rknn:
    type: rknn
    num_cores: 0

model:
  path: frigate-fp16-yolov9-t
  labelmap_path: /labelmap/coco-80.txt
  width: 320
  height: 320
  input_pixel_format: rgb
  input_tensor: nhwc
  input_dtype: int
  model_type: yolo-generic
```

Frigate successfully loaded the generated RKNN model from its persistent model cache. The following warning was observed immediately before the successful load:

```text
Query dynamic range failed. Ret code: RKNN_ERR_MODEL_INVALID.
```

Frigate notes that this warning can be ignored for a static-shape RKNN model. Treat the subsequent `Successfully loaded RKNN model` message as the important validation signal.

## Cameras and stream policy

The confirmed camera identifier is `front_yard`. It is a Reolink camera. A second camera was being added through the Frigate Add Camera Wizard, but its final identifier and operational state have not been confirmed in the documentation.

The desired camera pattern is:

- use a lower-resolution Reolink substream for detection;
- target approximately 5 detection frames per second;
- assign `detect` and `record` roles to the selected stream when using alert clips;
- allow UniFi Protect to keep the full-quality, continuous recording;
- retain only short Frigate clips needed to make Review alerts useful;
- track `person`, `bird`, `cat`, and `dog` initially;
- begin without motion masks or required zones, then add them based on observed false positives.

The `front_yard` RKNN detector and substream were operational. The exact live stream URLs and credentials are secrets and must not be committed to this repository.

Review items require recording to be enabled for the camera. The intended alert-only recording policy is:

```yaml
record:
  enabled: true
  continuous:
    days: 0
  motion:
    days: 0
  alerts:
    pre_capture: 5
    post_capture: 5
    retain:
      days: 7
      mode: motion
  detections:
    retain:
      days: 0
```

This is the agreed target policy, but it was not conclusively captured from the live configuration. Verify it in the Frigate UI before relying on seven-day retention. TR4's NVMe had approximately 220 GB free when Frigate was commissioned, which is ample for alert-only clips from the initial cameras.

## Wildlife observations and next steps

On 2026-09-26, the user reported that Frigate captured/detected kangaroos or wallabies and turkeys that morning. This is a user-reported observation; the clips, assigned object labels, scores, camera identifiers, and live configuration have not been independently inspected.

The documented YOLOv9 model uses COCO-80 labels, which do not include `kangaroo`, `wallaby`, or `turkey`. A turkey may be detected as `bird`; a kangaroo or wallaby may be assigned an incorrect supported label. Capturing the animal does not establish species recognition. Do not add unsupported species names to `objects.track` or rename a generic label as a substitute for training a model.

Recommended commissioning sequence (proposed work, not applied configuration):

1. **Review and preserve examples today.** Open the morning Review items and record camera, time, actual object label, score where available, Alert/Detection category, and whether the clip plays. Export a few useful examples before retention removes them. Include incorrect labels and missed sightings found in Protect. Record the installed Frigate version and confirm the second camera's identifier and stream roles.
2. **Verify retention before tuning.** Check the effective camera Record and Review settings against the target policy above. Under that policy, wildlife categorized only as Detections has no dedicated retained recording coverage. If wildlife clips are wanted, either include the relevant supported labels in Review Alerts, or deliberately adopt short Detection retention (for example, one or two days) and document the policy change. Review labels do not enable object tracking; the labels must also be tracked. Check a fresh wildlife clip and check it again the next day. Review Alerts are a category, not proof that a phone notification was sent.
3. **Collect a 48-72 hour baseline.** Keep the working RKNN/RKMPP setup and approximately 5 detection FPS while observing daylight, dusk, and night. Note useful detections, false positives, missed animals, pod restarts, FFmpeg errors, CPU/memory use, and daily media growth. Use Protect footage to investigate misses because Frigate's alert-only recordings cannot establish everything that passed the camera.
4. **Tune one camera and one setting at a time.** Define zones around the yard, driveway, or entry areas that matter and test them with an actual walk-through. Use required zones to scope alerts. Apply small motion masks only to persistent irrelevant motion, such as a timestamp or foliage; keep animal travel paths visible to motion detection. Adjust per-object confidence/size filters only after inspecting representative true and false detections, then repeat day/night checks. Filters cannot teach the model to recognize a kangaroo.
5. **Add notifications after Review is useful.** Start with a person entering the relevant property zone; decide separately whether wildlife warrants immediate delivery or just retained clips for browsing. Home Assistant is already in the homelab inventory, so its Frigate integration plus MQTT is a candidate, but neither the integration nor broker is confirmed. Alternatively use native browser notifications with trusted HTTPS. Test delivery, clip access, and duplicate suppression from a real event before relying on the path.
6. **Make the deployment recoverable.** Capture sanitized configuration and Kubernetes resources in this repository, record the running image version/digest rather than relying solely on the mutable `stable-rk` tag, and back up the required configuration/database with a tested restore procedure. Keep credentials outside Git. Confirm storage usage stabilizes after the configured retention window. Protect remains the authoritative video archive.

Species-specific recognition is a later task if generic animal clips prove insufficient. First establish what the current model actually calls the wildlife and collect representative images. Any replacement detector must be validated for Frigate's RKNN backend and TR4's resource budget; changing a label map alone does not add recognition capability.

Commissioning is complete when both intended cameras are documented, representative person/wildlife clips play with the intended retention, day/night behavior is understood, storage growth is bounded, and the selected notification and recovery paths have been tested (or explicitly deferred).

References checked on 2026-09-26: [available objects](https://docs.frigate.video/configuration/objects/), [Review categories](https://docs.frigate.video/configuration/review/), [recording retention](https://docs.frigate.video/configuration/record/), and [motion detection](https://docs.frigate.video/configuration/motion_detection/). Match configuration syntax and available UI controls to the installed Frigate version before applying changes.

## Configuration workflow

Use the Frigate Settings UI for ordinary camera changes:

1. Open **Settings -> Global configuration -> Camera management**.
2. Use **Add Camera** and select the Reolink template or probe the camera through ONVIF.
3. Test the stream and snapshot.
4. Assign stream roles, preferring the lower-resolution substream for `detect`.
5. Under **Camera configuration**, align Object Detection, Objects, Record, Review, and Streams settings with the established camera.
6. Save and restart Frigate when the UI indicates that a restart is required.

Global detector and hardware-acceleration settings should be inherited by cameras rather than duplicated unnecessarily. A camera-level tracked-object list replaces the inherited list; it does not append to it.

## Validation and operations

Log review on 2026-09-26: the supplied export ends at 13:51:00 Brisbane time after a restart. It reports Frigate `0.18.0-77a66e7`, successful RKNN model loading, and capture processes started for `front_yard` and `side_camera`. This confirms the second camera identifier, but does not establish sustained stream health. The export contains no MQTT log lines, so Frigate-to-broker publishing remains unverified. The user separately confirmed that the n8n MQTT credential connection test passed after creating dedicated Home Assistant MQTT users. Next validation is to receive `frigate/reviews` messages through an n8n MQTT Trigger during a real detection. A missing-email warning concerns native web push, not the selected MQTT-to-Discord path. A logging traceback occurs during shutdown before the successful startup; no post-startup traceback appears in the supplied tail.

Run Kubernetes commands from `PC3`, the current K3s server:

```bash
sudo k3s kubectl get pods -n frigate -o wide
sudo k3s kubectl logs -n frigate deployment/frigate --tail=200
sudo k3s kubectl top pod -n frigate
sudo k3s kubectl describe pod -n frigate -l app=frigate
```

On `TR4`, validate the persistent storage:

```bash
findmnt /mnt/k3s-storage
df -h /mnt/k3s-storage
sudo du -sh /mnt/k3s-storage/frigate/config
sudo du -sh /mnt/k3s-storage/frigate/media
```

Useful success indicators include:

- the Frigate pod is running on `TR4`;
- camera live view is stable;
- FFmpeg is not entering a watchdog restart loop;
- logs include `Successfully loaded RKNN model`;
- Review creates items after recording is enabled;
- media growth remains consistent with alert-only retention.

## Notifications

No external Frigate notification path is confirmed yet. Frigate Review items exist independently of browser push, Discord, Home Assistant, or other notification integrations.

Potential future approaches include:

- Frigate native browser notifications over a trusted HTTPS hostname;
- Home Assistant using the Frigate integration and MQTT;
- an MQTT, n8n, or Node-RED workflow that delivers selected events to Discord.

The existing Alertmanager-to-Discord integration belongs to the monitoring stack and does not automatically deliver Frigate camera events.

### n8n to Discord alerting (selected 2026-09-26)

The user is satisfied with initial detections and selected Discord as the first notification destination, using existing n8n on `dockerhost26`. Further detector tuning is not a prerequisite. This design is selected but not deployed.

The user confirmed Zigbee2MQTT uses `mqtt://core-mosquitto:1883` and Home Assistant is at `192.168.0.161`. External clients should use `192.168.0.161:1883`; `core-mosquitto` is the Home Assistant internal hostname. TCP connections from the workstation to `192.168.0.161:1883` and n8n at `192.168.0.160:5678` succeeded on 2026-09-26. MQTT authentication and reachability from the Frigate pod and n8n container are not yet verified.

Selected flow: **Frigate -> Mosquitto on Home Assistant -> n8n MQTT Trigger -> filters and duplicate suppression -> Discord**.

Setup sequence:

Staging decision: real trigger testing is currently deferred at the user's request. Prepare an inactive workflow using MQTT Trigger -> Code (parse payload and select completed Review items) -> Discord. For the initial draft, include both Alert and Detection review categories so wildlife is not silently excluded; this is a proposed default pending validation. Sending only on `type: end` delays delivery until activity finishes and avoids ordinary new/update notifications, but does not provide durable duplicate suppression against redelivery. Immediate alerts and persistent deduplication remain follow-up work. Do not describe this draft as tested or deployed.

1. Create dedicated non-administrator Home Assistant users `frigate_mqtt` and `n8n_frigate` under Settings -> People -> Users. Enable Advanced Mode in the profile if Users is hidden. Mosquitto supports Home Assistant user credentials. Store passwords privately; dedicated users alone do not impose topic ACLs.
2. In the chosen Discord server/channel, create a channel webhook under channel settings -> Integrations -> Webhooks. Save its URL directly into an n8n Discord Webhook credential. The URL is a secret; do not paste it into chat or documentation. The destination channel is not yet specified.
3. Configure Frigate MQTT against host `192.168.0.161`, port `1883`, with its dedicated credentials and a unique client ID. Inspect existing MQTT settings before editing. Store its password through the deployment's secret mechanism and use a supported Frigate environment placeholder. Prepare and validate changes before any restart; restarting Frigate requires confirmation under this repository's working agreement.
4. Create an n8n MQTT credential for the same host/port with user `n8n_frigate` and a different client ID. Subscribe to `frigate/reviews` and inspect an actual message before finalizing payload expressions. Confirm the configured topic prefix first.
5. Build filtering, persistent delivery state, and a Discord node using the saved webhook credential. Keep the workflow inactive until the intended Review categories and channel are confirmed. Start with text and a Frigate UI link; no image credentials or public ingress are required for a text-only notification.
6. Test delivery to the selected channel and duplicate handling, then activate and verify a real event. Record the workflow name, channel name (not webhook URL), chosen rules, and test result here. Neither a workflow nor credentials have been created yet.

Broker setup reference: [Home Assistant Mosquitto documentation](https://github.com/home-assistant/addons/blob/master/mosquitto/DOCS.md). Discord credential reference: [n8n Discord credentials](https://docs.n8n.io/integrations/builtin/credentials/discord/).

- Start with `frigate/reviews` (adjust for a non-default topic prefix). It supplies Review IDs, severity, cameras, objects, and zones, aligning routing with the Review UI. Process both new items and updates: an item can become an Alert after starting as a Detection.
- Store delivery state by Review ID and destination so repeated updates do not create repeated messages. Mark successful delivery, handle retries, and allow a deliberate escalation when an existing item becomes higher priority. A cooldown alone is not duplicate suppression.
- Candidate rules: immediate person alerts, wildlife messages to a separate destination or a scheduled digest, and quiet hours for non-urgent events. These are options pending user preference, not agreed rules. Use actual detector labels; n8n routing does not correct species identification.
- Start with camera, time, detected labels, and a link. Add snapshots/clips after authenticated media retrieval is tested; a completed clip may not exist at initial detection. Notification delivery and opening the linked media remotely are separate checks. Existing Teleport access can provide private access to links.
- n8n can deliver to Discord or coordinate with Home Assistant for phone notifications. It adds workflow flexibility but also depends on n8n and the broker being available. Test a new event, a Detection-to-Alert update, duplicate updates, delivery failure/retry, and remote link access before relying on it.
- Keep broker passwords, Frigate credentials, and destination tokens/webhook URLs in the appropriate secret or n8n credential store, never in committed workflow exports. Do not expose Frigate's unauthenticated port `5000` for this workflow.

References: [Frigate MQTT messages](https://docs.frigate.video/integrations/mqtt/), [n8n MQTT Trigger](https://docs.n8n.io/integrations/builtin/trigger-nodes/n8n-nodes-base.mqtttrigger/), and [n8n Discord node](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.discord/).

## Known limitations and follow-up work

- `TR4` is a single-node placement and storage dependency for Frigate. If TR4 or its NVMe fails, Frigate is unavailable even though Protect continues recording.
- The hostPath configuration and media directories are node-local and are not replicated by Kubernetes.
- The deployment is privileged and should be revisited only after the required Rockchip device permissions are fully understood.
- Do not expose Frigate port `5000`; use authenticated port `8971`/NodePort `30971` or a trusted reverse proxy.
- Confirm and document the second camera identifier and stream assignments.
- Capture the live Frigate configuration with secrets redacted.
- Move the Kubernetes resources out of `/tmp/frigate.yaml` into version control.
- Decide whether the configuration directory, retained alert clips, or both require backup. Protect remains the authoritative video archive.
- Configure masks, zones, object filters, and notifications only after daylight testing provides representative footage.
