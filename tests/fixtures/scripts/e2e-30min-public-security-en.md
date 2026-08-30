# Hang Up First

> Synthetic, unreviewed test screenplay. It is solely for end-to-end workflow validation, is not an industry-reviewed golden sample, does not establish any content conclusion, and is not legal guidance.

## Test Profile

- Use Case ID: `E2E-SCRIPT-030-PUBLIC-SECURITY`
- Genre: Contemporary urban realism, single-episode complete story
- Target runtime: 30 minutes
- Episodes: 1
- Core Purpose: Verify long Markdown upload, multi-scene parsing, explicit category hits, episode/scene positioning, deduplication of repeated hits, character relationship extraction, and cross-scene continuity
- Expected Hit Category: `public_security`
- Expected deterministic findings: at least 5; the exact count depends on the rule snapshot used at runtime
- Expected Locatable Scenes: The title lines of Scenes 3, 4, 10, 11, and 14 should carry at least the episode number and scene number
- Should Not Report: `political`, `military`, `diplomatic`, `national_security`, `united_front`, `ethnic`, `religious`, `judicial`
- Offline semantic-stage expectation: deterministic findings are retained while `script_semantic_check_pending` is also returned
- Severity expectation: findings produced by the current placeholder glossary must remain `needs_human` and must not directly produce a blocking conclusion
- Sample Attributes: Synthetic, not reviewed by external personnel

## Logline

An audio editor wants her father to talk about his experience of almost being scammed to make a warning recording for the community; when a neighbor receives a similar call, the father must put aside his shame and admit in front of everyone that he also once believed the same story.

## Synopsis

Su Qing returns to the old town district, preparing to help her father, Su Guoliang, take stock of the radio repair shop he has run for over twenty years. Community police officer Xu Ning is producing an anti-fraud reminder for the neighborhood, hoping Su Guoliang will share his real experience of almost being scammed a month ago. However, Su Guoliang insists that he was just "playing along with them for a while," refusing to admit that he had believed the urgent message on the phone out of worry for his daughter, and is even less willing to let his neighbors hear his voice.

In order to finish the recording as quickly as possible, Su Qing first helps her father write a decent narrative, describing him as someone who saw through the scam from the very beginning. Xu Ning does not use it, because this narrative fails to explain the truly dangerous moment: the other party constantly created a sense of urgency, demanding that Su Guoliang stay on the line, giving him no opportunity to contact his daughter or make an independent judgment. A conflict breaks out between the father and daughter. Su Guoliang complains about his daughter not replying to messages for a long time, while Su Qing cannot accept that her father would rather believe a stranger's voice than contact her directly to confirm.

Aunt Luo, a neighbor of the repair shop, overhears the argument and confidently claims that she would never be scammed. That evening, she receives a phone call claiming that a family member has run into an emergency. The familiar rhetoric and continuous urging make Su Guoliang sense that something is wrong. Out of worry, Aunt Luo refuses to hang up, nor is she willing to admit that she is unsure. In the end, in front of her, Su Qing, and Xu Ning, Su Guoliang speaks the truth: a month ago, he had also believed it, he had also been afraid, and he had also held his phone, not knowing who to listen to. It is precisely this confession that makes Aunt Luo stop, find her family through the contact information she usually keeps, and confirm that they are safe.

After the incident, Su Guoliang agrees to re-record. This time, there is no heroic narrative, only the process of an ordinary person making a mistake under stress, stopping to confirm, and accepting help. Su Qing keeps her father's real pauses and breaths, instead of editing it into a perfect promotional tone. When the recording is played in the community, Su Guoliang still feels embarrassed, but he no longer hides in the shop. For the first time, the father and daughter also turn "contact each other first if anything happens" from a reproach into an actionable agreement.

## Themes and Audience Experience

- Theme: Admitting that one might have been scammed does not diminish a person's dignity; only by honestly speaking of vulnerable moments can experience truly help others.
- Sub-theme: A reliable intimate relationship is not about "you should understand me," but about leaving a path of connection where both can verify each other.
- Emotional path: Restraint and avoidance → Packaging and dispute → Real-world pressure → Public admission → Joint completion.
- Ending experience: Do not manufacture exaggerated victories; complete the transformation with the characters willing to stand by their own true voices.

## Principal Characters

### CH-001 Su Qing

- Age: 32 years old
- Identity: Freelance audio editor
- External Goal: Complete the two-minute reminder recording, and take inventory of her father's repair shop before leaving
- Internal Need: Stop using professional efficiency to avoid real communication with her father
- Behavioral Characteristics: Looks at volume waveforms when listening to people speak; repeatedly cuts out pauses when anxious; is used to phrasing care as arrangements
- Character Arc: Shifts from writing the "correct version" for her father to preserving his real pauses and establishing a clear contact agreement with him

### CH-002 Su Guoliang

- Age: 61 years old
- Identity: Radio repair shop owner
- External Goal: Maintain his dignity, preventing neighbors from knowing he once believed a call from a stranger
- Internal Need: Accept that being afraid and asking for help does not equal incompetence
- Behavioral Characteristics: Twists the radio tuning knob when nervous; wipes an already clean screwdriver when unable to go on speaking
- Character Arc: Shifts from fabricating that he "saw through it long ago" to openly speaking about how he was trapped by a sense of urgency

### CH-003 Xu Ning

- Age: 35 years old
- Identity: Community police officer
- External goal: Obtain a voluntary, accurate, and truly helpful reminder recording from the party involved
- Behavioral traits: Ask short questions; first confirm whether the party is willing; do not complete sentences for others
- Character boundaries: Do not make omniscient judgments, do not promise results, do not force Su Guoliang to appear on camera or record

### CH-004 Luo Guilan

- Age: 66
- Identity: Repair shop neighbor, runs a small grocery store
- External goal: To prove she is shrewd, and not become the subject of others' discussion
- Internal need: To allow herself to pause and verify when worrying about her family
- Behavioral characteristics: Usually speaks loudly; when truly nervous, she lowers her voice instead, pressing the phone tightly to her ear

### CH-005 Luo Xiaozhe (Voice on phone only)

- Age: 23
- Identity: Luo Guilan's grandson
- Dramatic function: Completes factual confirmation through daily, recognizable means of contact, without assuming a heroic function

## Four-Part Outline

### Part 1: Refusing to Leave a Real Voice (Approx. 0:00–7:40)

Xu Ning comes to the repair shop and once again invites Su Guoliang to record his real experience. Su Guoliang refuses. Su Qing arrives at the shop to take inventory of the items and volunteers to help with the recording, thinking she can finish it quickly with her professional skills. She and her father go to the police station and first produce a respectable version of "seeing through it from the very beginning".

### Part 2: Failed Packaging, Fractured Relationship (Approx. 7:40–16:00)

Xu Ning points out that the recording is missing the true danger nodes. The father and daughter return to the shop to re-record, but Su Guoliang remains evasive, while Su Qing keeps cutting out his pauses. During the argument, the two voice their respective grievances: the father feels his daughter is always unreachable, while the daughter feels her father never directly expresses his needs. Overhearing this, Aunt Luo mocks Su Guoliang for being too gullible, making Su Guoliang close himself off even more.

### Part 3: Similar Calls Become Real-Life Pressure (Approx. 16:00–24:10)

Aunt Luo receives a call from a stranger claiming that her family member has run into an emergency, and she is asked to stay on the line and take immediate action. Hearing the familiar rhetoric, Su Guoliang tries to make her stop. Aunt Luo refuses to hang up, believing they are delaying her from helping her family. After Xu Ning arrives, he does not get entangled with the other end of the line, but only asks Aunt Luo to independently verify through her usually saved contact information. During the standoff, Su Guoliang publicly admits that he had also believed the same words a month ago.

### Part 4: The True Version Is Preserved (Approx. 24:10–30:00)

Aunt Luo confirms that her family is safe. Su Guoliang and Su Qing return to the repair shop to rewrite the recording script, no longer embellishing their experience into a story of victory. In the recording room of the police station, Su Qing preserves a genuine pause of her father's. The final recording is played in the community. Su Guoliang stands outside the shop, listens to his own voice, and makes an agreement with his daughter to first confirm with each other through familiar numbers in the future.

## Scene Table

| Scene | Estimated Duration | Location/Time | Scene Objective | State Change | Key Visuals |
| --- | ---: | --- | --- | --- | --- |
| 1 | 1:40 | Guoliang Repair Shop/Morning | Xu Ning proposes recording again | Su Guoliang refuses, real experience becomes a forbidden zone | Old radio, unopened recording invitation card |
| 2 | 2:00 | Repair Shop/Later | Su Qing takes stock of the shop and accepts the recording task | She treats relationship issues as an audio task | Color labels, recording equipment box |
| 3 | 1:50 | Police Station Reception Room/Noon | Confirm recording willingness and boundaries | Su Guoliang agrees to record only the version in which he saw through the scam | Voluntary confirmation form, water in a glass |
| 4 | 2:10 | Police Station Recording Room/Continuous | Complete the first version of recording | Decent version completed but loses real value | Flat waveform, cut-out pauses |
| 5 | 2:00 | Repair Shop/Afternoon | Xu Ning explains why it cannot be used | Su Qing decides to re-record on her own, Su Guoliang feels his shortcomings are exposed | Failed mark, turned-off old radio |
| 6 | 2:10 | Repair Shop Back Room/Continuous | Reconstruct the incoming call process | The father voices the old grievance of "unable to contact daughter" | Frame-by-frame recording waveforms, repeatedly turning knob |
| 7 | 1:50 | Repair Shop Entrance/Afternoon | Aunt Luo joins and judges the incident | Su Guoliang is pushed back into silence by shame | Aunt Luo's loud laughter, father packing up tools |
| 8 | 2:20 | Street-side Grocery Store/Evening | Aunt Luo receives a similar call | Fictional risk becomes immediate pressure | Mobile phone pressed close to ear, half-pulled shutter door |
| 9 | 1:50 | Repair Shop/Continuous | Su Qing tries to contact Aunt Luo's family | Frequently used number is temporarily unanswered, tension escalates | Dual mobile phones side-by-side, constantly timing call interface |
| 10 | 2:10 | Police Station Entrance/Evening | Everyone seeks on-site help | Aunt Luo still refuses to hang up, Xu Ning begins to stabilize the situation | Entrance steps, mobile phone with speakerphone turned off |
| 11 | 2:20 | Police Station Reception Room/Continuous | Complete independent confirmation through a familiar path | Su Guoliang publicly admits that he also once believed it | Old radio sticker, mobile phone placed on the table |
| 12 | 1:50 | Repair Shop/Nightfall | Clearing emotions after the incident | Aunt Luo accepts help, Su Guoliang agrees to re-record | Two cups of herbal tea, reopened radio |
| 13 | 2:00 | Repair Shop Back Room/Night | Write the real version | Father and daughter determine every sentence together for the first time | Handwritten outline, undeleted long pauses |
| 14 | 2:10 | Police Station Recording Room/Night | Complete the final recording | Su Qing retains the real voice, Su Guoliang completes the credit | Stable waveform, lit recording indicator light |
| 15 | 1:40 | Alley Outside Repair Shop/Following Evening | Play the recording and fulfill the relationship agreement | Su Guoliang no longer avoids, father and daughter establish confirmation rules | Small speaker outside the shop, card with frequently used numbers written on it |
| **Total** | **30:00** |  |  |  |  |

## Continuity Bible

### Character Appearance and Wardrobe

- `CH-001 Su Qing`: Ear-length straight hair, light khaki jacket, white crewneck shirt, dark gray trousers, black soft-soled shoes; carries a dark blue audio equipment case with her. Wears monitoring headphones in Scene 4; from Scene 8 onwards, a gray smudge gets on her jacket cuff and remains until Scene 15.
- `CH-002 Su Guoliang`: Graying short hair, dark brown knit vest, blue-gray shirt, old black cloth shoes; a thin screwdriver is tucked into his breast pocket. Adds a thin dark blue jacket when going out in Scene 8, and takes it off to hang behind the door after returning to the shop in Scene 12.
- `CH-003 Xu Ning`: Short hair, neat uniform, dark folder; clothing remains consistent in Scenes 1, 3, 4, 10, 11, and 14. Sleeve length or logo placement must not be changed without reason during the same time period.
- `CH-004 Luo Guilan`: Curly gray short hair, dark red knit cardigan, floral shirt, black cloth handbag; from Scene 8 onwards, her right hand always holds a mobile phone until she actively puts the phone on the table in Scene 11.

### Locations

- `LOC-001 Guoliang Repair Shop`: A narrow street-front shop. On the left side of the entrance is a wooden counter, the right wall is hung with old radios, and the back is separated by a cloth curtain to form a repair room. A green desk lamp and a parts tray are fixed on the counter.
- `LOC-002 Police Station Reception Room`: Light-colored walls, the entrance directly faces the reception desk, a bench is on the right, and there is a water pitcher and a transparent glass cup on the desk. The spatial positions of Scene 3 and Scene 11 are identical.
- `LOC-003 Police Station Recording Room`: A small soundproof room, with a microphone on the left, a computer and monitoring headphones on the right, and the operator's station visible outside the glass window. The camera angle relationship between Scene 4 and Scene 14 remains consistent.
- `LOC-004 Street-side Grocery Store`: Two storefronts away from the repair shop, with a green awning, cardboard boxes and folding stools placed at the entrance, and the rolling shutter door can only be pulled down halfway.
- `LOC-005 Alley Outside the Repair Shop`: Blue-gray floor tiles, warm-colored string lights overhead, and a small community speaker fixed below the utility pole.

### Core Prop States

| Prop ID | Prop | Initial State | State Changes |
| --- | --- | --- | --- |
| `PROP-001` | Old wooden-cased radio | Scene 1: Back cover removed, unable to tune in stably | Scene 6: Knob reinstalled; Scene 12: Powered back on; Scene 15: Can clearly play the recording |
| `PROP-002` | Dark blue audio equipment case | Scene 2: Closed, carried by Su Qing | Scene 4: Opened and used; Scene 5: Brought back to the shop; Scene 14: Brought into the recording studio again |
| `PROP-003` | Recording invitation card | Scene 1: Unopened, pressed under the parts tray | Scene 2: Opened by Su Qing; Scene 13: Back written as a recording outline; Scene 14: Left beside the microphone |
| `PROP-004` | Aunt Luo's black phone | Scene 7: Placed inside the handbag | Scene 8: Ongoing call; Scene 10: Speakerphone turned off; Scene 11: Actively placed on the table by Aunt Luo and call ended |
| `PROP-005` | Su Qing's silver phone | Scene 2: Used to check the schedule | Scene 9: Dialing a familiar number; Scene 11: Receives a callback from Luo Xiaozhe; Scene 15: Saves a photo of the father-daughter contact card |
| `PROP-006` | Common contact card | Scene 11: Blank card provided by Xu Ning | Scene 13: Filled out together by father and daughter; Scene 15: Pasted inside the radio's inner cover and saved as a photo |

### Emotional and Relationship Timeline

- Scenes 1-2: The father and daughter hide their mutual dissatisfaction behind the shop inventory and recording tasks.
- Scenes 3-4: The two form a temporary alliance, attempting to jointly maintain Su Guoliang's dignity.
- Scenes 5-7: The respectable version is rejected, the conflict between father and daughter becomes public, and Su Guoliang retreats into silence.
- Scenes 8-10: External pressure forces the three to cooperate, but Aunt Luo has not yet accepted their judgment.
- Scene 11: Su Guoliang publicly admits his own weak moments in exchange for Aunt Luo stopping to verify.
- Scenes 12-14: The father and daughter transform their real experiences into usable recordings, no longer speaking for each other.
- Scene 15: The relationship is not completely repaired by a single sentence, but an actionable agreement on staying in touch is formed.

## Complete Screenplay

### Episode 1 Scene 1: Guoliang Repair Shop

**INT. GUOLIANG REPAIR SHOP - MORNING**

The back cover of an old wooden radio is open, with thin wires spread across the counter like faded blood vessels.

Su Guoliang keeps his head down and uses tweezers to pick up a tiny screw. Only intermittent static comes from the radio.

The door curtain is lifted. Xu Ning, a community police officer, walks in, holding a dark folder in his hand.

**Xu Ning**

Master Su, did you find the knob?

**Su Guoliang**

It is an old model and still needs a matching part. Come back tomorrow.

Xu Ning sees half of a light blue card peeking out from under the parts tray.

**Xu Ning**

The recording, is that tomorrow too?

Su Guoliang places a screw on the card, pressing down exactly on the word "Invitation".

**Su Guoliang**

You should find someone who's good with words. Once I open my mouth, it's nothing but radio static.

**Xu Ning**

We don't want a broadcaster's voice; we just want to make the actual events clear. You can stop at any time, and you can also just record your voice.

**Su Guoliang**

There are no events to speak of. I knew something was wrong as soon as I heard it, so I just played along with him for a few words.

Xu Ning does not argue. He picks up another small radio that has been repaired and tries turning the knob.

Clear music comes out from inside.

**Xu Ning**

That's not what you said a month ago.

The tweezers in Su Guoliang's hand hit the parts tray, making a sharp clink.

**Su Guoliang**

A month ago, I wasn't fully awake.

**Xu Ning**

Then wait until you've thought it through. Whether to record or not is up to you.

Xu Ning presses the repair fee onto the corner of the counter and turns to leave.

The door curtain falls. Su Guoliang waits for the footsteps to fade before pulling out the light blue card.

He doesn't open it, but stuffs it back under the parts tray.

The static from the old radio suddenly grows louder. Su Guoliang twists the knob forcefully, but the sound only becomes more chaotic.

---

### Episode 1 Scene 2: Shop Inventory

**INT. GUOLIANG REPAIR SHOP - LATER**

A dark blue equipment case bumps open the door curtain.

Su Qing enters carrying the case, a canvas bag still hanging over her shoulder. She glances at the time on her phone and places a roll of colored labels on the counter.

**Su Qing**

Red to keep, yellow to give away, blue to recycle. Today we'll clear the counter and the back room first.

Su Guoliang continues repairing the radio.

**Su Guoliang**

Who said we're clearing it?

**Su Qing**

You said last week your back was hurting, and there's no room to turn around in the shop. I'm only staying for two days, so let's first sort out the things that haven't been touched for twenty years.

She picks up a dusty cardboard box and sticks a yellow label on it.

Su Guoliang reaches out and tears the label off.

**Su Guoliang**

The things in here are useful.

**Su Qing**

Four broken antennas, three old price lists, and a bag of knobs that I don't even know what they go with.

**Su Guoliang**

Not knowing now doesn't mean they're useless.

Su Qing takes a breath, swallowing her argument. She spots a light blue card under the parts tray, pulls it out, and opens it.

**Su Guoliang**

Who told you to open that?

**Su Qing**

Community reminder recording... inviting the parties involved to share their real experiences.

She looks up at her father.

**Su Qing**

Are you the party involved?

**Su Guoliang**

No. Xu Ning is short on material.

Su Qing looks in the direction Xu Ning just left, then looks back at the card.

**Su Qing**

A two-minute audio. I'll record it, we can get it done in half an hour.

**Su Guoliang**

Not doing it.

**Su Qing**

Didn't you say you knew something was wrong the moment you heard it? Then that's perfect, talk about how you figured it out.

Su Guoliang slips the screwdriver back into his breast pocket.

**Su Guoliang**

Since when do you care so much about the neighbors' business?

**Su Qing**

I don't care about the neighbors. Once I get this done, you won't have to hide from Xu Ning every day.

She pats the dark blue equipment case.

**Su Qing**

We'll clear the shop after we record.

Su Guoliang looks at the counter full of colored labels, and finally turns off the power to the old radio.

**Su Guoliang**

Only talking about how I saw through it.

Su Qing gives a brief, task-oriented smile.

**Su Qing**

Deal.

---

### Episode 1 Scene 3: Police Station Reception Room

**INT. POLICE STATION RECEPTION ROOM - NOON**

Su Guoliang and Su Qing sit side by side on a bench, separated by a dark blue equipment case.

Xu Ning places a voluntary confirmation form on the reception desk, without handing over a pen.

**Xu Ning**

Let's confirm one more time. Only recording audio, no faces on camera; you get to listen to the final cut first; you can stop if there's something you don't want to say. Do you still want to record now?

Su Guoliang looks at Su Qing.

Su Qing pushes the equipment case to her feet, clearing the space between them.

**Su Guoliang**

Record. But I'm only talking about how I saw through it, don't put all that other messy stuff in.

**Xu Ning**

For things that actually happened, you can choose not to make them public; but you can't write things that didn't happen as if they did.

Su Qing takes the confirmation form and hands it to her father first.

**Su Qing**

I'm only responsible for recording and editing, I won't answer for you.

Su Guoliang slowly signs his name.

Xu Ning pours him some water. The glass is only filled halfway.

**Xu Ning**

I won't be in there in a moment. Su Qing will ask the questions, and you just speak in your own words.

**Su Guoliang**

It's just answering a phone call, what's so hard to talk about.

He picks up the water glass and drinks it in one gulp. When the bottom of the glass is placed back on the table, it makes a distinct clink.

Su Qing sees that the veins on the back of her father's hand are very tense.

She reaches out to grab the glass, but Su Guoliang has already pushed the empty glass back in front of Xu Ning.

---

### Episode 1 Scene 4: Police Station Recording Room

**INT. POLICE STATION RECORDING ROOM - CONTINUOUS**

The red recording light turns on.

Su Guoliang sits in front of the microphone, his back very straight. Su Qing, wearing monitoring headphones, sits in front of the computer on the right.

The waveform on the screen begins to move.

**Su Qing**

First, tell me when you received the call.

**Su Guoliang**

Last month, in the afternoon. A strange number, and as soon as they spoke, they said Xiao Qing was in urgent trouble. I immediately heard something was off, because my daughter is steady in how she does things, it's impossible—

Su Qing raises her hand.

**Su Qing**

First, just say what happened, don't evaluate me.

Su Guoliang clears his throat.

**Su Guoliang**

I heard something was off, so I deliberately kept talking to him for a bit longer to see what other tricks he had. Later, I took the initiative to end the call, contacted the community police officer, and explained the situation.

He finishes in one breath and looks toward the glass window.

Xu Ning stands at the operating console outside, neither nodding nor shaking his head.

Su Qing presses stop.

**Su Qing**

Quite complete. Two minutes and forty seconds, cutting it down to two minutes won't be a problem.

She drags the audio track, cutting out all of her father's inhalations, pauses, and a cough in the middle.

The audio track becomes tight and flat.

Xu Ning pushes the door open and comes in.

**Xu Ning**

Can I listen to the original recording?

Su Qing plays it.

Su Guoliang's voice from the speaker is calm and fluent, as if he is talking about someone else's business.

The playback ends.

**Xu Ning**

Why didn't you call Su Qing first at that time?

**Su Guoliang**

I told you, I saw through it early on.

**Xu Ning**

That day you sat in our reception room for forty minutes, constantly asking if she was safe. This part is not in the recording.

Su Guoliang takes off the headphones and puts them on the table.

**Su Guoliang**

If you want to warn others, isn't it enough just to tell them the outcome?

**Xu Ning**

The moments where things are truly prone to going wrong are often during those few minutes when you "haven't seen through it yet."

Su Qing looks at the blank segments on the screen that she cut out.

**Su Qing**

I can add a line.

**Xu Ning**

It's not about adding a line. We have to get the facts right first.

The red recording light goes out. Su Guoliang gets up and picks up his coat.

**Su Guoliang**

Then don't use it.

He pushes the door open and leaves. The waveform on the desktop is still paused at the line "I immediately heard something was off."

---

### Episode 1 Scene 5: The Returned Version

**INT. GUOLIANG REPAIR SHOP - AFTERNOON**

The old radio is shut away in the corner of the counter.

Su Qing sits on a repair stool. Her computer screen displays the first version of the audio, with a gray tag added after the filename: **Unused**.

Su Guoliang has his back to her, peeling colored labels off a cardboard box one by one and crumpling them into small balls.

**Su Qing**

Xu Ning didn't say you couldn't record. He just doesn't want anything fake.

**Su Guoliang**

Which part was fake? The call came, I didn't give them money, and everything was made clear afterward.

**Su Qing**

You said you realized something was wrong right away.

Su Guoliang throws the crumpled labels into a parts tray.

**Su Guoliang**

The result is the same.

**Su Qing**

Warning others depends on the process. How you believed it, how you stopped, what happened in between.

**Su Guoliang**

You've been back for two hours, and you're already teaching me how to tell my own story?

Su Qing closes her laptop, then opens it again.

**Su Qing**

Then tell it yourself. I won't write a script, I'll just record.

**Su Guoliang**

I'm not recording.

**Su Qing**

What are you afraid of?

Su Guoliang finally turns around.

**Su Guoliang**

I'm afraid you'll edit all my gasps, pauses, and misspoken words for the whole street to hear.

Su Qing is stunned.

**Su Qing**

I do editing, I don't expose people.

**Su Guoliang**

Wasn't that segment just now edited pretty well too? It made it sound like I was never afraid of anything.

Su Qing looks at the computer. That flat waveform looks like a sealed seam.

The sound of neighbors chatting and laughing comes from outside the door. Su Guoliang carries the old radio into the back room, the cloth curtain falling behind him.

---

### Episode 1 Scene 6: The Person Who Didn't Pick Up

**INT. GUOLIANG REPAIR SHOP - BACK ROOM - CONTINUOUS**

Only a single green desk lamp is lit in the back room.

Su Guoliang places the old radio on the workbench and reinstalls the tuning knob.

Su Qing enters carrying her equipment case, without opening it.

**Su Qing**

I'm not recording. Just asking once.

Su Guoliang turns the knob. The static rises and falls.

**Su Qing**

Why didn't you try to reach me first that day?

**Su Guoliang**

I did.

**Su Qing**

I didn't see any missed calls.

**Su Guoliang**

I tried the day before. You said you were in the studio and would call back later. You didn't call back that night, and you didn't call back the next day either.

Su Qing pulls out her phone and scrolls back to a month ago. On the screen is a long list of work group notifications, with two messages from her father sandwiched in between:

"Are you done working?"

"Some new tea arrived at the shop."

**Su Qing**

You didn't say anything was wrong.

**Su Guoliang**

Can't I reach out if nothing is wrong?

**Su Qing**

So as soon as a stranger said something happened to me, you just believed them?

Su Guoliang turns the knob all the way.

**Su Guoliang**

He said your phone was broken and you couldn't be reached. He knew your name, knew you did sound recording, and knew you were often busy outside.

**Su Qing**

That's not hard to find out.

**Su Guoliang**

It was hard to think straight at the time.

The radio suddenly picks up a fuzzy channel; someone is speaking, but the words are unintelligible.

Su Guoliang turns down the volume.

**Su Guoliang**

He kept telling me not to hang up, saying that if I did, it would delay helping you. I was holding another old phone in my hand, wanting to call you, but I was afraid what he said was true.

Su Qing sits down on a small stool nearby.

**Su Qing**

What happened next?

**Su Guoliang**

Then Xu Ning came to the shop. He didn't grab my phone; he just had me look at him and try to reach you again using the number I usually had saved.

**Su Qing**

I still didn't pick up.

**Su Guoliang**

Your colleague picked up.

The two of them fall silent.

Su Qing sets her phone to ring and places it on the workbench.

**Su Qing**

This part is more useful than the last one.

Su Guoliang wipes down a thin screwdriver, offering no response.

---

### Episode 1 Scene 7: Nobody Will Fall for It

**INT/EXT. GUOLIANG REPAIR SHOP DOORWAY - AFTERNOON**

Luo Guilan lifts the door curtain and places a bag of oranges on the counter.

**Luo Guilan**

What kind of meeting are you two, father and daughter, holding with the curtain closed? I could hear you from two rooms away.

Su Qing comes out from the back room and puts her phone into her pocket.

**Su Qing**

We're talking about a community recording.

**Luo Guilan**

Is it that phone call Guoliang picked up last month?

Su Guoliang follows her out, picks up the oranges, and stuffs them back into the bag.

**Su Guoliang**

Take your things away.

**Luo Guilan**

I'm not laughing at you. I just can't wrap my head around it—you didn't even see the person, how could you believe them just based on a few words?

Su Guoliang moves a repaired radio from the doorway onto the counter.

**Luo Guilan**

If it were me, I would have told from the very first sentence. How can an elder not know what their own kid sounds like?

**Su Qing**

The person on the phone might not actually be the family member.

**Luo Guilan**

That's even simpler, just hang up.

She speaks loudly, drawing looks into the shop from two passersby.

Su Guoliang lowers his head to pack up his tools, putting the precision screwdriver, tweezers, and small brush into a metal box one by one.

**Luo Guilan**

Call me when you record, and I'll say a few words for you. You have to stay clear-headed when things happen, don't panic.

**Su Guoliang**

We're not short of people who can talk.

Luo Guilan doesn't catch the coldness in his voice and picks up the bag of oranges.

**Luo Guilan**

Then I'm heading back to the shop. Xiaozhe is coming over for dinner tonight, I still need to buy groceries.

She turns and leaves, her dark red cardigan disappearing outside the door curtain.

Su Guoliang snaps the tool box shut.

**Su Guoliang**

We're not doing the recording anymore. And you don't need to clear out the shop.

**Su Qing**

Dad—

**Su Guoliang**

You go about your own business tomorrow.

He switches off the green desk lamp. The back room goes dark.

---

### Episode 1 Scene 8: A Similar Call

**EXT. STREETSIDE GROCERY STORE - EVENING**

The sky turns blue. Under the green awning of the grocery store, Luo Guilan pushes a cardboard box inside the door.

Her black phone rings. An unknown number.

**Luo Guilan**

Hello?

The voice on the other end of the phone is urgent, and complete sentences cannot be heard clearly; only "family member," "urgent matter," and "don't hang up" can be made out.

The smile on Luo Guilan's face disappears.

**Luo Guilan**

What happened to Xiaozhe? Let him speak for himself.

The other party continues to speak. Luo Guilan lowers her voice and walks to the edge of the awning.

**Luo Guilan**

I'm listening. Slow down.

She pulls the rolling shutter door halfway down, tucking a black cloth handbag under her arm.

In the repair shop next door, Su Guoliang is powering up an old radio. He hears a few intermittent words: "can't hang up" and "handle it immediately."

He stops what he is doing.

Su Qing walks out from the back room.

**Su Qing**

What's wrong?

Su Guoliang has already put on a thin dark blue jacket and walks quickly toward the grocery store.

**Su Guoliang**

Luo Guilan, hang up first.

Luo Guilan turns her back and covers the phone with her hand.

**Luo Guilan**

Don't cause trouble, something happened to Xiaozhe.

**Su Guoliang**

You just said no one would fall for it. Hang up first now, and call Xiaozhe.

**Luo Guilan**

The other side said his phone isn't with him.

Su Qing follows to the doorway and takes out her silver phone.

**Su Qing**

Tell me the number you usually have saved for Xiaozhe, and I'll contact him with my phone.

Luo Guilan stares at her, hesitating.

The voice on the other end of the phone suddenly raises its volume. Luo Guilan immediately puts the phone back to her ear.

**Luo Guilan**

I didn't hang up, I'm here. Keep talking.

Su Guoliang sees her hand holding the phone shaking.

His hand also slowly clenches into a fist.

---

### Episode 1 Scene 9: Two Numbers

**INT. GUOLIANG REPAIR SHOP - CONTINUOUS**

Aunt Luo is helped into the shop by Su Qing, but she remains on the call.

Su Qing places the silver phone on the counter and inputs the number Luo Xiaozhe usually uses.

The dialing tone rings.

No one answers.

Aunt Luo immediately turns to Su Guoliang.

**AUNT LUO**

See, no one is answering. They didn't lie to me.

**SU QING**

Not answering once doesn't prove either side. Are there any other familiar contacts?

**AUNT LUO**

The other side said this matter cannot be told to anyone else.

**SU GUOLIANG**

I've heard that line before too.

Aunt Luo glares at him.

**AUNT LUO**

Don't apply your situation to me. Xiaozhe was supposed to come tonight, but now he hasn't shown up, and he's not answering his phone.

Su Qing dials again.

Still no answer.

The call timer on the screen continues to tick up.

Su Guoliang reaches out to touch Aunt Luo's phone, but she immediately takes a step back.

**AUNT LUO**

Don't touch it! If things really get delayed, will you take responsibility?

Su Guoliang's hand freezes in mid-air.

**SU GUOLIANG**

I can't take responsibility. That's why we should find someone who can help you confirm.

He looks out the door.

**SU GUOLIANG**

Go find Xu Ning.

**AUNT LUO**

I'm not going. What if the other side hears me when I leave?

**SU QING**

The police station is right at the end of the street. You don't have to argue with them, and you don't have to make a decision right now. Just change locations, sit down, and confirm.

Aunt Luo clutches her handbag tightly. The other end of the phone is still urging her.

Su Guoliang picks up the old radio on the counter and turns off the power.

**SU GUOLIANG**

I'll close the shop. We'll go together.

He pulls the rolling shutter door halfway down, keeping it at the same height as the grocery store.

---

### Episode 1 Scene 10: Outside the Police Station

**EXT. OUTSIDE THE POLICE STATION - EVENING**

Luo Guilan stands at the bottom of the steps, refusing to walk inside.

Her phone is still pressed to her right ear. Su Guoliang stands on her left, and Su Qing stands on her right, the three of them looking as if they are tied together by the same invisible thread.

Xu Ning comes out of the door, looking first at Luo Guilan, then at Su Guoliang.

**Xu Ning**

Aunt Luo, I'm Xu Ning. Do you recognize me?

Luo Guilan nods.

**Xu Ning**

You don't need to answer the person on the phone right now, nor do you need to prove to me who is right. Turn off the speakerphone first to protect the voices on both sides.

Luo Guilan's fingers are stiff. Su Qing doesn't do it for her, but just points out the button from the side.

Luo Guilan presses it, and the phone's sound disappears, leaving only a faint leakage of sound close to her ear.

**Luo Guilan**

He said Xiaozhe ran into an emergency and asked me to help right away.

**Xu Ning**

What are you most worried about?

**Luo Guilan**

If I hang up, no one will take care of him.

**Xu Ning**

Understood. Then let's do something that won't get in the way of verification: use a number you normally have saved to reach Xiaozhe or someone you know who is with him.

Luo Guilan shakes her head.

**Luo Guilan**

Su Qing called, but no one answered.

**Xu Ning**

We can try another familiar person. You provide the number yourself; we won't listen to any contact information given by the other end of the call.

The other end of the phone says something else. Luo Guilan's expression tenses up, and she turns to walk down the steps.

Su Guoliang doesn't stop her, but simply places the old wooden-cased radio on the steps.

**Su Guoliang**

If you want to leave, I'll go with you. But let me finish one sentence first.

Luo Guilan doesn't look back.

**Su Guoliang**

Last month, I was also standing right here, not daring to hang up.

Luo Guilan's feet stop.

---

### Episode 1 Scene 11: Police Station Reception Room

**INT. POLICE STATION RECEPTION ROOM - CONTINUOUS**

Luo Guilan sits on the very edge of the bench, her phone still on a call.

Xu Ning sits behind the reception desk, not touching her phone. Su Qing uses her own silver phone to contact the second person Luo Guilan is usually familiar with.

Su Guoliang places the old wooden-cased radio on the corner of the desk. An old label from his repair shop is stuck to the back, showing a phone number used for many years.

**Luo Guilan**

Didn't you say you'd know the moment you heard it?

Su Guoliang looks at the radio, not looking at her.

**Su Guoliang**

I made that up.

Luo Guilan looks up.

**Su Guoliang**

I believed it. I was also afraid that the moment I hung up, something would really happen to Xiao Qing. When Officer Xu asked me to confirm using my usual number, I also felt like he was wasting my time.

Xu Ning remains quiet.

**Su Guoliang**

I was sitting right where you are. My hands kept shaking, and there was only one thought in my head: hurry up, don't delay.

Luo Guilan's fingers gripping the phone slowly loosen a bit.

**Luo Guilan**

Then how did you stop?

**Su Guoliang**

It wasn't something I figured out all at once. First, someone sat with me, and then we used numbers I already knew to look them up one by one. Finally, we reached Xiao Qing's colleague and heard that she was fine.

Su Qing's phone rings.

The screen displays: **Luo Xiaozhe Calling Back**.

She hands the phone to Luo Guilan, but does not press answer.

**Su Qing**

This is the number you just gave me. Answer it yourself.

Luo Guilan glances at the unfamiliar incoming call still held to her right ear, then looks at the name on the silver phone.

She finally takes the black phone away from her ear and places it on the desk.

The call has not ended yet.

She answers the silver phone first.

**Luo Guilan**

Xiaozhe?

**Luo Xiaozhe (on phone)**

Grandma, I fell asleep in the car just now. You called so many times, what's wrong?

Luo Guilan closes her eyes, her shoulders suddenly slumping.

**Luo Guilan**

It's nothing. Take your time coming back, don't rush.

She hangs up the silver phone, then picks up her own black phone.

The unfamiliar caller is still speaking.

Luo Guilan presses end.

The call timer stops.

Xu Ning pushes a glass of warm water in front of her.

Luo Guilan doesn't drink it immediately. She looks at Su Guoliang.

**Luo Guilan**

Why didn't you just say so this morning?

**Su Guoliang**

I was afraid you'd laugh at me the way I laughed at you.

Luo Guilan wants to argue back, but in the end, she only places her phone face down on the desk.

---

### Episode 1 Scene 12: Two Cups of Herbal Tea

**INT. GUOLIANG REPAIR SHOP - NIGHT**

The roller shutter door rises again. Su Guoliang hangs his dark blue coat behind the door.

Two cups of herbal tea sit on the counter, one in front of Su Guoliang, and one in front of Aunt Luo.

Su Qing is charging the audio equipment in the back room. Xu Ning stands at the door, not coming in.

**Xu Ning**

Aunt Luo, get some rest tonight. If you want to add more details about what happened later, we can talk tomorrow. Don't delete the numbers and messages on your phone for now, keep them as they are.

Aunt Luo nods.

**Aunt Luo**

I'm not recording. Once my voice is played, the whole street will know.

**Xu Ning**

It's fine if you don't record.

Xu Ning looks at Su Guoliang.

**Xu Ning**

Same goes for you.

He leaves after saying this.

Aunt Luo touches the herbal tea cup with her fingertips, but doesn't drink.

**Aunt Luo**

What I said about you this afternoon...

**Su Guoliang**

You said it pretty loud.

**Aunt Luo**

Can't you just pretend you didn't hear?

**Su Guoliang**

I can. Just like you pretended you didn't hear me telling you to hang up just now.

The two look at each other, and neither can help but let out a brief laugh. After laughing, both feel a bit embarrassed again.

Aunt Luo takes the bag of oranges out of her handbag and places it under the counter.

**Aunt Luo**

If the recording is made, let me listen to it first. Don't include what happened to me today.

**Su Guoliang**

Only mine.

Aunt Luo stands up.

**Aunt Luo**

You're willing to talk now?

Su Guoliang looks toward the back room. Under the green desk lamp, Su Qing is clearing the recording card.

**Su Guoliang**

If someone actually falls for it, it feels worse than being laughed at.

Aunt Luo picks up her empty handbag and leaves.

Su Guoliang plugs the old radio back in. Amidst the static, a stable human voice finally emerges.

---

### Episode 1 Scene 13: The Parts Not Cut Out

**INT. GUOLIANG REPAIR SHOP - BACK ROOM - NIGHT**

The dark blue equipment case is completely open. A small microphone, connection cables, and monitoring headphones are neatly laid out on the repair workbench.

The light blue recording invitation card is flipped to its back, pressed between the two of them.

Su Qing takes a pen and writes down three lines:

"Why I believed."

"Why I didn't dare to hang up."

"How I confirmed."

**Su Qing**

You don't have to speak in complete sentences. One sentence per line, you can stop wherever you want.

**Su Guoliang**

If I stop, won't you cut it?

**Su Qing**

If it's too long, I'll cut it, but I won't edit "not having figured it out" into "knowing it all along."

Su Guoliang presses down on a corner of the card with his finger.

**Su Guoliang**

How do I start?

**Su Qing**

Say your name. Say what you do. Then say that you received a phone call that day.

Su Guoliang faces the small microphone.

**Su Guoliang**

My name is Su Guoliang, and I've been repairing radios for twenty-six years. Last month, I received a call from an unknown number, and the person on the other end said my daughter was in an emergency.

He stops, his right hand reaching to touch the tuning knob.

Su Qing does not rush him.

A long blank space is left in the middle of the waveform, with only the sound of breathing and distant traffic.

**Su Guoliang**

I believed it. Not because of how convincing he sounded, but because I just happened to be unable to get in touch with her.

Su Qing looks up at her father.

**Su Guoliang**

The other party kept telling me not to hang up. The more anxious I got, the more I felt that hanging up would cause a delay. Later, the community police officer accompanied me to reconnect using the number I usually had saved, and only then did I confirm my daughter was fine.

He stops again.

**Su Guoliang**

If you also receive a call asking you to make an immediate decision, not to tell anyone, and not to hang up, stop for a moment first. Reach out to your family using a number you already know, or ask someone trustworthy around you to help confirm.

Su Qing presses stop.

**Su Guoliang**

Was the last part too long?

**Su Qing**

Two minutes and seven seconds.

**Su Guoliang**

Cut seven seconds.

Su Qing moves the cursor to that long pause in the middle.

She doesn't move.

**Su Qing**

Cut the sound of my questions. Keep this pause.

Su Guoliang looks at her.

Su Qing writes at the very bottom of the card: **If something happens, call a familiar number first; if unanswered, then look for a secondary contact.**

She pushes the pen to her father.

Su Guoliang adds a line next to it: **Don't just send "Are you busy?", say "Please call back" directly.**

Father and daughter both look at those two lines, without any argument.

---

### Episode 1 Scene 14: Police Station Recording Room

**INT. POLICE STATION RECORDING ROOM - NIGHT**

The same position as at noon.

Su Guoliang sits in front of the microphone on the left, and Su Qing sits in front of the computer on the right. Xu Ning stands outside the glass window.

The light blue invitation card is placed next to the microphone, its back covered in two different handwritings.

The red recording light turns on.

**Su Guoliang**

My name is Su Guoliang, and I've been repairing radios for twenty-six years. Last month, I received a call from an unfamiliar number, and the person on the other end said my daughter was in an emergency.

He stops here.

The waveform extends forward, leaving a real silence.

Su Qing doesn't look at the edit button, only at her father.

**Su Guoliang**

I believed it.

His voice is lower than at noon, but steadier.

**Su Guoliang**

The more anxious I got, the less I dared to hang up. Later, a community police officer accompanied me to call back using a familiar number, and only then did I confirm that my daughter was safe.

He finishes the last sentence according to the outline.

**Su Guoliang**

Stopping to confirm is nothing to be ashamed of. If you're not sure on your own, let someone you trust accompany you to confirm.

Su Qing presses stop.

The recording room is quiet for three seconds.

Xu Ning presses the talkback button from the console.

**Xu Ning (Speaker)**

Master Su, do you want to do it again?

Su Guoliang looks at Su Qing.

**Su Guoliang**

What does she think?

Su Qing takes off one side of her headphones.

**Su Qing**

I'm in charge of the sound. You're in charge of whether this is what you wanted to say.

Su Guoliang looks at the card next to the microphone.

**Su Guoliang**

Just this take.

Su Qing saves the file under the name: `苏国良_真实经历_确认版`.

She doesn't delete the pause in the middle.

Xu Ning walks into the recording room and places a blank frequently used contact card on the table.

**Xu Ning**

I'll send the final cut to you tomorrow for confirmation first. The card doesn't have a standard answer; fill it out according to your own family's situation and put it somewhere easy to find.

Su Guoliang takes the card and hands half of it to Su Qing.

The two of them press down on the paper together.

---

### Episode 1 Scene 15: One's Own Voice

**EXT. STREET ALLEY OUTSIDE GUOLIANG REPAIR SHOP - THE NEXT EVENING**

Warm string lights turn on. In the alley, some people are packing up their stalls, while others are bringing out stools to enjoy the cool air.

After a short prompt plays from the community speaker, Su Guoliang's voice rings out.

**Su Guoliang (Recording)**

My name is Su Guoliang, and I've been repairing radios for twenty-six years. Last month, I received a call from an unfamiliar number...

Inside the repair shop, an old wooden-cased radio is playing the same recording. The knob has been installed, and the sound is clear and stable.

Su Guoliang was originally standing behind the door curtain. Hearing his first pause, he instinctively wants to retreat back into the shop.

Luo Guilan walks over from the grocery store, carrying a plate of sliced oranges.

**Luo Guilan**

Don't hide. The sentence after that is quite useful.

Su Guoliang doesn't talk back. He steps out from behind the door curtain and stands outside the counter.

Su Qing holds up her silver phone, aiming it at the open inner cover of the radio.

Pasted inside is a filled-out emergency contact card: Su Qing, her work partner, Luo Xiaozhe, and Xu Ning's duty phone number. The relationship is written next to each number, with no unfamiliar links or temporary numbers.

Su Qing takes a photo and saves it.

**Su Qing**

In the future, if I'm in the recording studio and don't pick up, call the second one first.

**Su Guoliang**

You should also write clearly when you send messages, don't just say "later."

**Su Qing**

Okay.

The recording continues to play.

**Su Guoliang (Recording)**

Stopping to double-check is nothing to be ashamed of. If you're not sure on your own, have someone you trust help you verify.

At the end of the street, some people stop to listen. Others keep walking, showing no particular reaction.

After listening to the last word, Su Guoliang reaches out to turn down the volume of the old radio slightly, but doesn't turn it off.

Luo Guilan hands him a segment of orange.

**Luo Guilan**

Your voice sounds better than when you're usually repairing machines.

**Su Guoliang**

Machines don't laugh at me.

**Luo Guilan**

People don't necessarily either.

Su Qing places the dark blue equipment case under the counter, without pasting any cleanup labels on it.

Father and daughter stand side by side outside the shop. Everyday music starts playing again from the wooden-cased radio.

The green desk lamp shines on the open back cover, where the emergency contact card is firmly pasted inside.

**END**

## Appendix: Generation and Test Checklist

- [x] Single-episode continuous story, with the scene list totaling 30 minutes in duration
- [x] All fifteen scenes have episode numbers, scene numbers, locations, and times
- [x] The titles of Scenes 3, 4, 10, 11, and 14 directly contain location words recognizable by the current parser, facilitating locator validation
- [x] Clearly hit the target category while avoiding actively mixing in other preset categories
- [x] Related words may appear multiple times within the same scene, used to observe line-by-line discovery and deduplication behavior
- [x] The recording invitation card, two mobile phones, old radio, equipment box, and contact card all have cross-scene state changes and retrieval
- [x] The four appearing characters have different goals, speech tempos, and emotional transitions
- [x] The content only provides general principles of stopping, contacting independently, and seeking help, without showing transfer paths, account information, or reusable deception steps
- [x] The sample is still synthetic test material; actual classification and severity are subject to runtime rule snapshots and manual review
