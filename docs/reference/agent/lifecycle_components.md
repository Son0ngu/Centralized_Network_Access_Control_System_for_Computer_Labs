# Agent lifecycle components

Cap nhat: 2026-05-27

## Muc tieu

`agent/core/lifecycle.py` khong con la mot ham start/stop gom tat ca side effect. Vong doi agent da co contract component ro rang:

- `AgentComponent.name`
- `AgentComponent.start(context)`
- `AgentComponent.stop(context)`
- `AgentComponent.health(context)`

`initialize_components(config, runtime=None)` van la public API cu, nhung ben trong chi tao `LifecycleContext` va goi `start_components(...)` theo thu tu component.

## Contract chinh

| Symbol | File | Vai tro |
| --- | --- | --- |
| `LifecycleContext` | `agent/core/lifecycle.py` | Context runtime/config/result/started_components duoc truyen vao moi component. |
| `AgentComponent` | `agent/core/lifecycle.py` | Base contract cho lifecycle component. |
| `build_default_components()` | `agent/core/lifecycle.py` | Tra ve thu tu production components. |
| `start_components(context, components)` | `agent/core/lifecycle.py` | Start tung component theo thu tu; neu fail thi stop cac component da start. |
| `stop_components(context)` | `agent/core/lifecycle.py` | Stop nguoc thu tu `started_components`. |
| `initialize_components(config, runtime=None)` | `agent/core/lifecycle.py` | API production/backward-compatible; set config, start stack, mark running. |
| `cleanup(config=None, runtime=None)` | `agent/core/lifecycle.py` | API production/backward-compatible; stop stack da luu tren runtime. |

## Production components

Thu tu start hien tai:

1. `RegistrationComponent`
2. `TokenManagerComponent`
3. `WhitelistComponent`
4. `FirewallComponent`
5. `LogSenderComponent`
6. `HeartbeatComponent`
7. `PacketSnifferComponent`

Thu tu stop la nguoc lai. `WhitelistComponent` gom ca whitelist manager, sync lan dau, va periodic sync de giu invariant cu: whitelist phai sync truoc khi firewall enable default deny.

## Failure behavior

`start_components(...)` co ba rule quan trong:

- Component duoc append vao `context.started_components` ngay truoc khi goi `start()`, vi `start()` co the mutate runtime roi moi raise.
- Neu component raise exception, lifecycle record `STATUS_FAILED`, stop nguoc ca component dang start do va cac component da start truoc no, roi raise ve `initialize_components`.
- Neu component khong raise nhung ghi `STATUS_FAILED` vao `InitResult`, lifecycle cung coi do la start failure va cleanup stack da start.

`initialize_components(...)` catch exception va tra ve `InitResult` nhu cu, nen caller legacy van dung duoc `if not initialize_components(...)`.

## Test coverage

`agent/tests/test_lifecycle_components.py` cover:

- start order dung va runtime luu stack component.
- stop order nguoc voi start order.
- start fail se cleanup chi nhung component da start.
- component ghi `STATUS_FAILED` se kich hoat cleanup.

Lenh regression:

```powershell
.venv\Scripts\python.exe -m pytest agent\tests\test_lifecycle_components.py -q
```

## Huong mo rong

Khi them component moi:

- Tao class subclass `AgentComponent`.
- Dat `name` on dinh de log/test health khong doi ngau nhien.
- `start()` chi nen mutate `context.agent` va `context.result`.
- `stop()` phai idempotent, khong raise neu handle da `None`.
- Them vao `build_default_components()` dung vi tri dependency.
- Them fake-component test neu component co thu tu hoac cleanup quan trong.
