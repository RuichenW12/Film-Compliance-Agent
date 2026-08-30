# Hang Up First

> Synthetic, unreviewed test screenplay for end-to-end workflow validation only. It is not an expert-reviewed golden sample, does not state a content-compliance conclusion, and is not legal guidance.

## Test Profile

- Case ID: `E2E-SCRIPT-030-PUBLIC-SECURITY`
- Type: contemporary urban realist drama; one complete episode
- Target runtime: 30 minutes
- Episodes: 1
- Primary purpose: validate long Markdown upload, multi-scene parsing, explicit category hits, episode/scene location, within-scene deduplication, relationship extraction, and cross-scene continuity
- Expected category key: `public_security`
- Expected deterministic hits: at least 5; the exact number depends on the runtime policy snapshot
- Expected locatable scenes: the headings for Scenes 3, 4, 10, 11, and 14 must carry episode and scene coordinates
- Must not report: `political`, `military`, `diplomatic`, `national_security`, `united_front`, `ethnic`, `religious`, or `judicial`
- Offline semantic-stage expectation: retain deterministic findings and return `script_semantic_check_pending`
- Severity expectation: findings from the current placeholder glossary remain `needs_human` and must never become automatic blocking conclusions
- Sample status: synthetic and unreviewed by external professionals

## Logline

An audio editor wants her father to describe how he nearly fell for a scam so she can make a neighborhood warning. When a neighbor receives a similar call, he must set aside his shame and admit in public that he once believed the same story.

## Synopsis

Su Qing returns to the old neighborhood to inventory the radio-repair shop her father, Su Guoliang, has run for more than twenty years. Community police officer Xu Ning is making an anti-fraud recording and asks Guoliang to describe a call that nearly deceived him one month earlier. Guoliang insists that he merely played along and refuses to admit that fear for his daughter made him believe the caller.

Qing drafts a dignified account in which her father recognizes the fraud immediately. Xu Ning rejects it because it omits the dangerous interval when the caller created urgency, demanded that Guoliang stay on the line, and prevented independent confirmation. Father and daughter clash: he resents her unanswered messages, while she cannot accept that he trusted a stranger instead of contacting her directly.

Their neighbor Aunt Luo boasts that she could never be fooled. That evening she receives a call claiming that her grandson is in trouble. Guoliang recognizes the pressure tactics. Luo refuses to hang up until Guoliang admits that he too believed, feared, and did not know whom to trust. His honesty lets her pause, call a familiar number, and confirm that her grandson is safe.

Guoliang records the warning again without turning himself into a hero. Qing keeps his real pauses and breaths. When the recording plays in the lane, he is embarrassed but no longer hides. Father and daughter turn “contact each other first” from an accusation into a practical plan.

## Theme and Audience Experience

- Theme: admitting vulnerability to deception does not destroy dignity; an honest account of a weak moment can help someone else.
- Secondary theme: reliable intimacy requires a usable path for confirmation, not the assumption that loved ones should simply understand.
- Emotional path: restraint and avoidance → packaging and conflict → immediate pressure → public admission → shared completion.
- Ending: no exaggerated victory; Guoliang changes by standing beside his own truthful voice.

## Principal Characters

### CH-001 Su Qing

- Age: 32
- Role: freelance audio editor
- External goal: finish a two-minute warning and inventory the shop before leaving
- Internal need: stop using professional efficiency to avoid a real conversation with her father
- Behavior: watches waveforms while people speak; cuts pauses when anxious; disguises concern as scheduling
- Arc: replaces the “correct version” she wrote for him with his truthful pauses and a concrete contact agreement

### CH-002 Su Guoliang

- Age: 61
- Role: owner of a radio-repair shop
- External goal: preserve his dignity and keep neighbors from learning that he believed a stranger's call
- Internal need: accept that fear and asking for help are not incompetence
- Behavior: twists a tuning knob when tense; wipes an already clean screwdriver when words fail
- Arc: moves from claiming he knew immediately to explaining publicly how urgency trapped him

### CH-003 Xu Ning

- Age: 35
- Role: community police officer
- External goal: obtain a voluntary, accurate, genuinely useful warning recording
- Boundary: asks short questions, confirms consent, never finishes another person's sentence, promises no outcome, and never forces Guoliang to appear or record

### CH-004 Luo Guilan

- Age: 66
- Role: neighboring grocery-shop owner
- External goal: prove that she is shrewd and will never become the subject of gossip
- Internal need: permit herself to pause and verify when afraid for family
- Behavior: normally loud; under real pressure she lowers her voice and presses the phone to her ear

### CH-005 Luo Xiaozhe (voice only)

- Age: 23
- Role: Luo Guilan's grandson
- Dramatic function: provides ordinary independent confirmation through a familiar saved number, never a heroic rescue

## Four-Part Outline

1. Refusing the real voice (0:00–7:40): Xu Ning renews the invitation. Qing treats the recording as a quick technical task, and father and daughter create an “I knew all along” version.
2. The package fails (7:40–16:00): Xu Ning identifies the missing dangerous moment. During a second attempt, Guoliang reveals his resentment over Qing's silence. Aunt Luo mocks him, driving him back into shame.
3. A similar call (16:00–24:10): Luo is ordered to stay on a call and act immediately. Guoliang recognizes the words. Xu Ning asks her only to verify through a familiar route. Guoliang publicly admits that he once believed the same story.
4. Keeping the truthful version (24:10–30:00): Luo confirms that Xiaozhe is safe. Guoliang rerecords without heroics. Qing preserves his pause, and they create a practical contact card.

## Scene Table

| Scene | Runtime | Place / time | Scene purpose | State change | Key image |
| --- | ---: | --- | --- | --- | --- |
| 1 | 1:40 | Guoliang's shop / morning | Xu renews the invitation | Guoliang refuses | open radio, sealed invitation |
| 2 | 2:00 | shop / later | Qing inventories and takes the task | she treats conflict as audio work | colored labels, equipment case |
| 3 | 1:50 | police reception room / noon | confirm consent | Guoliang permits only the heroic version | consent form, half-full glass |
| 4 | 2:10 | police recording room / continuous | record draft one | polished version loses truth | flat waveform, deleted pause |
| 5 | 2:00 | shop / afternoon | explain rejection | Qing chooses to rerecord; Guoliang feels exposed | rejected marker, silent radio |
| 6 | 2:10 | back room / continuous | reconstruct the call | he reveals resentment about unanswered messages | waveform blocks, turning knob |
| 7 | 1:50 | shop doorway / afternoon | Luo judges the incident | shame closes Guoliang down | loud laugh, packed tools |
| 8 | 2:20 | grocery / dusk | Luo receives a similar call | abstract risk becomes immediate | phone at ear, half shutter |
| 9 | 1:50 | shop / continuous | Qing calls family | no answer raises pressure | two phones, call timer |
| 10 | 2:10 | police-station entrance / dusk | seek help | Luo still refuses to hang up | steps, speakerphone off |
| 11 | 2:20 | reception room / continuous | confirm independently | Guoliang admits he believed | old radio label, phone on table |
| 12 | 1:50 | shop / nightfall | settle after the event | Luo accepts help; Guoliang agrees to record | two teas, powered radio |
| 13 | 2:00 | back room / night | write the truthful version | father and daughter choose every line together | handwritten outline, long pause |
| 14 | 2:10 | recording room / night | record the final version | Qing keeps the truth; Guoliang signs his name | steady waveform, red light |
| 15 | 1:40 | lane / next dusk | play it and honor the agreement | Guoliang no longer hides | speaker, contact card |
| **Total** | **30:00** |  |  |  |  |

## Continuity Bible

- Su Qing: straight chin-length hair, light khaki jacket, white crewneck, charcoal trousers, black soft-soled shoes, navy audio case. A gray mark appears on her cuff in Scene 8 and remains through Scene 15.
- Su Guoliang: short graying hair, dark-brown vest, blue-gray shirt, worn black cloth shoes, fine screwdriver in breast pocket. He adds a navy jacket in Scene 8 and hangs it behind the door in Scene 12.
- Xu Ning: short hair, neat uniform, dark folder; identical appearance in Scenes 1, 3, 4, 10, 11, and 14.
- Luo Guilan: short gray curls, dark-red cardigan, floral blouse, black cloth bag. From Scene 8 through Scene 11 her right hand holds the phone until she places it down herself.
- Shop: long narrow storefront, wood counter left, old radios on right wall, curtained workroom behind, fixed green lamp and parts tray.
- Reception room: pale walls, desk opposite entrance, bench to the right, water jug and clear glasses. Scenes 3 and 11 use the same geography.
- Recording room: microphone left, computer and headphones right, operator visible behind glass. Scenes 4 and 14 mirror positions.
- Grocery: two doors away, green awning, boxes and folding stool, shutter that only closes halfway.
- Props: `PROP-001` old radio is open in Scene 1, receives its knob in Scene 6, powers on in Scene 12, and plays clearly in Scene 15; `PROP-002` audio case opens in Scenes 4 and 13–14; `PROP-003` invitation is opened in Scene 2 and becomes the outline in Scene 13; `PROP-004` Luo's black phone stays on the call until Scene 11; `PROP-005` Qing's silver phone makes the familiar-number calls; `PROP-006` contact card is supplied in Scene 14 and photographed in Scene 15.

## Complete Screenplay

### Episode 1 Scene 1: Guoliang's Repair Shop

**INT. GUOLIANG'S REPAIR SHOP — MORNING**

The back of an old wooden radio lies open. Fine wires spread across the counter. SU GUOLIANG lifts a tiny screw with tweezers while static breaks in and out. XU NING enters with a dark folder.

**XU NING**

Master Su, find the knob?

**SU GUOLIANG**

Old model. Needs a match. Come tomorrow.

Xu spots a pale-blue invitation under the parts tray. Guoliang pins the word “Invitation” beneath a screw.

**XU NING**

The recording too—tomorrow?

**SU GUOLIANG**

Find someone who can talk. I open my mouth and all you get is radio static.

**XU NING**

We want what happened, not an announcer. You can stop whenever you want, and record voice only.

**SU GUOLIANG**

Nothing happened. I knew it was wrong and played along.

Xu tests a repaired radio; clear music emerges.

**XU NING**

That isn't what you said a month ago.

The tweezers strike the tray.

**SU GUOLIANG**

I wasn't awake a month ago.

**XU NING**

Then wait until you're sure. Recording is your choice.

After Xu leaves, Guoliang pulls out the sealed card, hides it again, and twists the tuning knob. The static worsens.

### Episode 1 Scene 2: Inventory

**INT. GUOLIANG'S REPAIR SHOP — LATER**

A navy equipment case pushes through the curtain. SU QING enters, checks the time, and puts colored labels on the counter.

**SU QING**

Red stays, yellow is donated, blue is recycled. Counter and back room today.

**SU GUOLIANG**

Who said we were clearing anything?

She labels a dusty box. He tears the label off: four broken antennas, three price books, a bag of unmatched knobs—all useful someday, he says. Qing swallows the argument and opens the invitation.

**SU QING**

A community warning recording. You were involved?

**SU GUOLIANG**

No. Xu Ning needs material.

**SU QING**

Two minutes. I can record it in half an hour.

He refuses. She reminds him that he claims to have recognized the fraud immediately.

**SU GUOLIANG**

Since when do you manage the neighbors?

**SU QING**

I finish this, you stop hiding from Xu. Then we clear the shop.

He turns off the old radio.

**SU GUOLIANG**

Only how I recognized it.

**SU QING**

Deal.

### Episode 1 Scene 3: Police Reception Room

**INT. POLICE RECEPTION ROOM — NOON**

Father and daughter sit on a bench with the equipment case between them. Xu places a voluntary-consent form on the desk but does not offer a pen.

**XU NING**

Voice only, no face. You hear the finished piece first. Stop wherever you want. Do you still want to record?

Qing moves the case to the floor, opening the space between them.

**SU GUOLIANG**

Yes, but only how I spotted it. Leave the mess out.

**XU NING**

You may withhold what really happened. You may not replace it with something that did not.

Qing gives the form to her father.

**SU QING**

I record and edit. I don't answer for you.

Guoliang signs. Xu pours half a glass of water. Guoliang drains it in one gulp; the glass knocks sharply against the desk.

### Episode 1 Scene 4: First Recording

**INT. POLICE RECORDING ROOM — CONTINUOUS**

The red light comes on. Guoliang sits rigidly at the microphone; Qing watches the waveform.

**SU QING**

When did the call come?

**SU GUOLIANG**

Last month. A stranger said you were in trouble. I knew at once—

**SU QING**

Say what happened. Don't evaluate me.

He delivers a smooth account: he recognized the trick, prolonged the call to study it, ended it himself, and informed the community police. Qing cuts every breath, cough, and pause until the waveform is flat. Xu listens to the raw take.

**XU NING**

Why didn't you call Qing first?

**SU GUOLIANG**

I said I knew.

**XU NING**

You sat in reception for forty minutes asking whether she was safe. The recording omits that.

**SU GUOLIANG**

For a warning, isn't the outcome enough?

**XU NING**

The dangerous part is often the few minutes before you know.

**SU QING**

I can add a sentence.

**XU NING**

First make the facts right.

Guoliang leaves. The screen freezes on “I knew at once.”

### Episode 1 Scene 5: Rejected Version

**INT. GUOLIANG'S REPAIR SHOP — AFTERNOON**

The file is marked **NOT USED**. Guoliang tears labels from boxes.

**SU QING**

Xu didn't say you couldn't record. He said no fiction.

**SU GUOLIANG**

I sent no money and reported it. Same result.

**SU QING**

The process is the warning: why you believed, what stopped you.

He accuses her of returning for two hours and teaching him his own story. She offers to record without a script. He refuses.

**SU QING**

What are you afraid of?

**SU GUOLIANG**

That you'll play my breathing, pauses, and wrong words to the whole street.

**SU QING**

I edit. I don't hang people out for display.

**SU GUOLIANG**

The first cut sounded excellent—like I was never afraid.

He carries the radio behind the curtain. Qing stares at the sealed, even waveform.

### Episode 1 Scene 6: The Person Who Did Not Answer

**INT. SHOP BACK ROOM — CONTINUOUS**

Under the green lamp, Guoliang reinstalls the tuning knob. Qing enters with the closed equipment case.

**SU QING**

I'm not recording. One question: why didn't you call me?

**SU GUOLIANG**

I did the day before. You said you'd call after the studio. You didn't.

Her phone shows his buried messages: “Finished work?” and “New tea at the shop.”

**SU QING**

You didn't say it mattered.

**SU GUOLIANG**

May I call only when something matters?

The stranger knew Qing's name, her audio work, and her travel. He said her phone was broken and ordered Guoliang not to hang up. Guoliang held a second phone but feared that calling might delay help.

**SU GUOLIANG**

At the time, thinking was hard.

Xu arrived, did not seize the phone, and asked him to use a familiar saved number. Qing still did not answer; a colleague did.

Qing switches her phone to ring and puts it on the bench.

**SU QING**

That is more useful than the first recording.

He wipes the screwdriver and says nothing.

### Episode 1 Scene 7: Nobody Gets Fooled

**INT./EXT. SHOP DOORWAY — AFTERNOON**

LUO GUILAN brings oranges and loudly asks about last month's call. Guoliang pushes the bag back.

**LUO GUILAN**

I don't mock you. I just cannot understand believing words from someone you've never seen. I'd know in the first sentence.

**SU QING**

The caller may not sound like your relative.

**LUO GUILAN**

Then hang up. Simple.

Passersby look in. Guoliang packs each tool into a metal box. Luo volunteers to record advice about staying calm, then leaves to buy food for her grandson Xiaozhe.

**SU GUOLIANG**

No recording. No need to clear the shop. Do your work tomorrow.

He switches off the green lamp.

### Episode 1 Scene 8: A Similar Call

**EXT. STREET GROCERY — DUSK**

Under the green awning, Luo answers an unknown number. Fragments escape: “family,” “emergency,” “don't hang up.” Her smile vanishes.

**LUO GUILAN**

What happened to Xiaozhe? Let him speak.

She lowers her voice and pulls the shutter halfway down. Next door, Guoliang hears “cannot hang up” and “act now.” He puts on his navy jacket.

**SU GUOLIANG**

Luo Guilan, hang up first.

**LUO GUILAN**

Don't interfere. Xiaozhe is in trouble. They say his phone isn't with him.

Qing offers to call Xiaozhe's saved number from her silver phone. Luo hesitates; the caller raises his voice, and she presses the phone back to her ear.

**LUO GUILAN**

I didn't hang up. Keep talking.

Guoliang watches her hand shake. His own fist closes.

### Episode 1 Scene 9: Two Numbers

**INT. GUOLIANG'S REPAIR SHOP — CONTINUOUS**

Luo remains on the call. Qing dials Xiaozhe's usual number twice. No answer.

**LUO GUILAN**

See? They didn't lie.

**SU QING**

One missed call proves neither side. Who else do you know?

**LUO GUILAN**

They said I must tell no one.

**SU GUOLIANG**

I heard that sentence too.

Luo warns him not to impose his mistake on her. When he reaches toward her phone, she recoils.

**LUO GUILAN**

If your delay harms him, are you responsible?

**SU GUOLIANG**

I cannot be. That is why we find someone who can help confirm.

They propose the station at the corner. Guoliang lowers his shop shutter to the same height as hers and goes with her.

### Episode 1 Scene 10: Police-Station Entrance

**EXT. POLICE-STATION ENTRANCE — DUSK**

Luo refuses to climb the steps, phone at her right ear. Guoliang and Qing stand on either side. Xu approaches.

**XU NING**

Aunt Luo, do you recognize me? You need not answer the caller or prove who is right. Turn off speakerphone first to protect both sides' voices.

Luo operates her own phone while Qing only points to the button.

**LUO GUILAN**

He says Xiaozhe needs immediate help. If I hang up, nobody will help him.

**XU NING**

Then do one thing that does not obstruct confirmation: use a number you already saved to reach him or someone you know beside him.

The caller presses again. Luo turns to leave. Guoliang does not block her; he sets the old radio on the step.

**SU GUOLIANG**

If you go, I go. But hear one sentence first. Last month I stood here too, afraid to hang up.

She stops.

### Episode 1 Scene 11: Independent Confirmation

**INT. POLICE RECEPTION ROOM — CONTINUOUS**

Luo sits at the edge of the same bench. Xu never touches her phone. Qing calls a second familiar contact. Guoliang puts the old radio on the desk, its shop label showing a long-used number.

**LUO GUILAN**

Didn't you say you knew immediately?

**SU GUOLIANG**

I invented that. I believed. I feared that hanging up would make Qing's trouble real. I thought Officer Xu was delaying me too.

He sat in Luo's exact seat, hands shaking, with only “hurry” left in his mind. He stopped not through sudden insight but because someone sat with him and called familiar numbers one by one.

Qing's screen shows **LUO XIAOZHE — RETURNING CALL**. She hands the phone to Luo without answering it.

**SU QING**

This is the number you gave me. You answer.

Luo places the black phone on the desk, still connected, and answers the silver one.

**LUO XIAOZHE (PHONE)**

Grandma, I fell asleep on the bus. Why so many calls?

**LUO GUILAN**

Nothing. Come slowly. Don't rush.

She ends the stranger's call herself. Xu offers warm water.

**LUO GUILAN**

Why didn't you say this this morning?

**SU GUOLIANG**

I feared you'd laugh at me the way I laughed at you.

She turns the phone face down instead of arguing.

### Episode 1 Scene 12: Two Cups of Cold Tea

**INT. GUOLIANG'S REPAIR SHOP — NIGHTFALL**

The shutter rises. Guoliang hangs his jacket behind the door. Two cups of cold tea sit on the counter. Xu tells Luo to rest, preserve the number and messages unchanged, and speak later only if she wishes. Recording is optional for both of them.

**LUO GUILAN**

I won't record. The whole lane would know my voice.

After Xu leaves, Luo tries to apologize for speaking so loudly.

**SU GUOLIANG**

You could pretend you didn't hear me.

**LUO GUILAN**

You could pretend you didn't hear what I said.

They laugh briefly, both embarrassed. Luo leaves the oranges under the counter and asks to hear Guoliang's recording first—without adding her incident.

**SU GUOLIANG**

Only mine. Someone truly facing it feels worse than being laughed at.

He powers on the radio; a stable voice emerges through the static.

### Episode 1 Scene 13: The Part We Do Not Cut

**INT. SHOP BACK ROOM — NIGHT**

The equipment case is fully open. On the invitation's back, Qing writes: “Why I believed. Why I feared hanging up. How I confirmed.”

**SU QING**

One sentence each. Pause wherever you need.

**SU GUOLIANG**

And you won't cut the pause?

**SU QING**

I may shorten it. I will not edit “I didn't understand” into “I always knew.”

At the small microphone, he gives his name and twenty-six years repairing radios, then stops. Qing waits through breathing and distant traffic.

**SU GUOLIANG**

I believed because I could not reach her. The caller kept saying not to hang up. The more urgent it felt, the more hanging up felt like delay. A community officer stayed with me while I used saved numbers to confirm she was safe.

He advises listeners to pause when ordered to decide immediately, keep a call secret, or remain connected, and to use a previously known contact or seek trusted help. The take is two minutes seven seconds.

Qing keeps the long pause and cuts her own questions. She writes, “If something happens, call a familiar number; if unanswered, call a second contact.” Guoliang adds, “Don't text only ‘Busy?’ Say ‘Please call me.’” They do not argue.

### Episode 1 Scene 14: Final Recording

**INT. POLICE RECORDING ROOM — NIGHT**

Positions match noon. The invitation, filled in two handwritings, lies beside the microphone. The red light comes on.

**SU GUOLIANG**

My name is Su Guoliang. I have repaired radios for twenty-six years. Last month a stranger called and said my daughter was in trouble.

He pauses. The waveform advances through truthful silence.

**SU GUOLIANG**

I believed. The more anxious I became, the less I dared hang up. A community police officer helped me switch to a familiar number and confirm that my daughter was safe. Pausing to verify is not shameful. If you are uncertain, ask someone you trust to confirm with you.

After three seconds of silence, Xu asks over the speaker whether he wants another take.

**SU GUOLIANG**

What does she think?

**SU QING**

I am responsible for the sound. You decide whether these are your words.

He keeps the take. Qing saves `Su_Guoliang_true_account_confirmed` without removing the pause. Xu supplies a blank familiar-contact card and explains that each family should fill its own; there is no universal answer. Father and daughter hold opposite edges.

### Episode 1 Scene 15: His Own Voice

**EXT. LANE OUTSIDE GUOLIANG'S SHOP — NEXT DUSK**

Warm string lights glow. A community speaker and the repaired wooden radio play Guoliang's recording. At his first pause, he starts to retreat behind the curtain. Luo arrives with orange slices.

**LUO GUILAN**

Don't hide. The next sentence is useful.

He stands outside. Qing photographs the contact card fixed inside the radio: Qing, her work partner, Luo Xiaozhe, and Xu Ning's duty number, each labeled by relationship with no unfamiliar links or temporary numbers.

**SU QING**

If I'm in the studio and don't answer, call the second person.

**SU GUOLIANG**

And write clearly. Don't say only “later.”

The recording says that pausing and asking for trusted help are not shameful. Some neighbors stop; others keep walking. Guoliang turns the volume down but does not switch it off.

**LUO GUILAN**

Your voice sounds better than when you repair machines.

**SU GUOLIANG**

Machines don't laugh at me.

**LUO GUILAN**

People may not either.

Qing places the equipment case under the counter without an inventory label. Father and daughter stand together as ordinary music returns. The green lamp illuminates the open radio and the contact card fixed firmly inside.

**END**

## Appendix: Generation and Test Checklist

- [x] One continuous episode; scene-table runtime totals 30 minutes.
- [x] All 15 scenes have episode number, scene number, place, and time.
- [x] Scenes 3, 4, 10, 11, and 14 use directly parseable location headings.
- [x] The target machine key appears explicitly without deliberately mixing other seeded categories.
- [x] Repeated relevant language inside one scene supports line-level discovery and deduplication checks.
- [x] Invitation, two phones, old radio, equipment case, and contact card change state and pay off across scenes.
- [x] Four speaking characters have distinct goals, rhythms, and emotional turns.
- [x] The material gives only general pause, independent-contact, and help-seeking principles; it contains no transfer route, account information, or reusable deception steps.
- [x] This remains synthetic, unreviewed test material. Actual classification and severity depend on the runtime snapshot and human review. It is not legal guidance.
