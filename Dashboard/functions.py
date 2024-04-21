import os
import pickle
import datetime
import numpy as np
import utils as ut
import pandas as pd
import streamlit as st
import imageio.v3 as iio
import matplotlib.pyplot as plt
import matplotlib.patches as patches

import functions as fct
import scripts.calc_features as feat

# import utils as ut


# -----------------------------------------------------------------------------
# region PATIENT DATABASE -----------------------------------------------------
# -----------------------------------------------------------------------------
def add_pat(name, age):
    if name == "":
        return False

    # handle name
    name.strip()

    # new patient
    new_pat = pd.DataFrame(
        {"id": 1, "name": name, "age": int(age), "n_rec": 0, "last_rec": 0},
        index=[0],
    )

    # handle adding patient to DB
    dbl = list(st.session_state.pat_db.index)
    if len(dbl) == 0:
        if st.session_state.debug:
            print("empty db")
        st.session_state.pat_db = new_pat
    else:
        if st.session_state.debug:
            print(f"{len(dbl)} patients in db")
        new_pat["id"] = max(st.session_state.pat_db["id"]) + 1
        st.session_state.pat_db = pd.concat(
            [st.session_state.pat_db, new_pat], axis=0, ignore_index=True
        )

    # save updated DB
    st.session_state.pat_db.to_csv(os.path.join("files", "patients.csv"), index=False)

    st.session_state.patient_list = [
        f"{int(r['id'])}: {r['name']} (age: {int(r['age'])})"
        for (_, r) in st.session_state.pat_db.iterrows()
    ]
    return True


def update_pat_DB():
    print(st.session_state.pat_db_update)
    # st.session_state.pat_db = st.session_state.pat_db_update
    # st.session_state.pat_db.to_csv(os.path.join("files", "patients.csv"), index=False)

    return True


def del_patient(x):
    print(x)
    del_id = int(x.split(":")[0])
    del_idx = st.session_state.pat_db.id == del_id
    st.session_state.pat_db = st.session_state.pat_db.loc[np.invert(del_idx), :]
    st.session_state.pat_db.to_csv(os.path.join("files", "patients.csv"), index=False)

    if st.session_state.debug:
        print(" id to delete: " + str(del_id))
        print(del_idx)
        print(st.session_state.pat_db.loc[del_idx, :])
        print(st.session_state.pat_db.loc[np.invert(del_idx), :])

    return True


# -----------------------------------------------------------------------------
# region RECORDING ------------------------------------------------------------
# -----------------------------------------------------------------------------
def example_load_scanpath(kind: str, img: int, sp_idx: int) -> list:
    # path to scanpath file
    sp_path = os.path.join(
        "..",
        "data",
        "Saliency4ASD",
        "TrainingData",
        kind,
        f"{kind}_scanpath_{img}.txt",
    )

    # read scanpat*.txt file
    sp = pd.read_csv(sp_path, index_col=None)
    sp.columns = map(str.strip, sp.columns)
    sp.columns = map(str.lower, sp.columns)

    starts = np.where(sp["idx"] == 0)[0]
    ends = np.append(starts[1:], len(sp))
    all_sp = [sp[start:end] for start, end in zip(starts, ends)]

    return all_sp[sp_idx]


def load_scanpath(sp_path: str) -> list:
    # read scanpat*.txt file
    sp = pd.read_csv(sp_path, index_col=None)
    sp.columns = map(str.strip, sp.columns)
    sp.columns = map(str.lower, sp.columns)

    starts = np.where(sp["idx"] == 0)[0]
    ends = np.append(starts[1:], len(sp))
    all_sp = [sp[start:end] for start, end in zip(starts, ends)]

    return all_sp


def save_recording(pat, kind):
    kind = "ASD" if kind == "ASD" else "TD"

    # patient, img & scanpath vars
    pat_id = int(pat.split(":")[0])
    images = st.session_state.opt["images"]
    sps = (
        st.session_state.opt["sp_idx_asd"]
        if kind == "ASD"
        else st.session_state.opt["sp_idx_td"]
    )

    # get scanpaths
    df_sp = None
    for img in images:
        sp = example_load_scanpath(kind, img, sps[img])
        sp["img"] = img
        df_sp = pd.concat([df_sp, sp], ignore_index=True)

    # save csv file
    dt = datetime.datetime.today().strftime("%Y-%m-%d_%H-%M-%S.csv")
    name = f"id-{pat_id}_{dt}"
    df_sp.to_csv(os.path.join("recordings", f"{name}"), index=False)

    # save session state
    if st.session_state.last_saved_recording is None:
        st.session_state.last_saved_recording = name


def update_rec_DB():
    tmp = st.session_state.pat_db.copy()
    for p in st.session_state.patient_list:
        id = int(p.split(":")[0])

        recs = st.session_state.rec_db[p][0]
        n_rec = len(recs)

        tmp.loc[tmp["id"] == id, "n_rec"] = n_rec
        if n_rec > 0:
            last_rec = st.session_state.rec_db[p][1][-1]
            tmp.loc[tmp["id"] == id, "last_rec"] = last_rec
        else:
            tmp.loc[tmp["id"] == id, "last_rec"] = "---"

    # save updated DB
    tmp.to_csv(os.path.join("files", "patients.csv"), index=False)


# -----------------------------------------------------------------------------
# region ANALYSIS -------------------------------------------------------------
# -----------------------------------------------------------------------------
def extract_features():
    # filename
    id = st.session_state.eval_pat.split(":")[0]
    rec_date = ut.ugly_date(st.session_state.eval_meas)
    csv_file = os.path.join("recordings", f"id-{id}_{rec_date}.csv")

    # curdir = os.path.dirname(__file__)
    # csv_file = os.path.join(curdir, "recordings", "id-1_2024-01-08_17-22-45.csv")

    # extract features
    df = feat.scanpath(csv_file)
    df_sal = feat.saliency(csv_file)
    df_obj = feat.objects(csv_file)

    df = df.merge(df_sal, on="img")
    df = df.merge(df_obj, on="img")

    return df


def clean_features(df):
    # set id as index
    df = df.set_index("img", drop=True)
    df = df.drop(
        columns=[col for col in df.columns if "_obj" in col]
    )  # drop 'object' columns
    df = df[df["sp_fix_duration_ms_total"] <= 5000]

    return df


def load_classifiers():
    clf = {
        "RF": pickle.load(open(os.path.join("models", "RF.pickle"), "rb")),
        "XGB": pickle.load(open(os.path.join("models", "XGB.pickle"), "rb")),
        "SVC": pickle.load(open(os.path.join("models", "SVC.pickle"), "rb")),
        "NB_s": pickle.load(open(os.path.join("models", "NB_s.pickle"), "rb")),
        "KNN_s": pickle.load(open(os.path.join("models", "KNN_s.pickle"), "rb")),
    }
    return clf


def predict(df, clf):
    pred = []
    proba = []

    for img in df.index.tolist():
        X = df.loc[[img]]
        mdl = st.session_state.img2mdl[img]["mdl"]
        if "_s" in mdl:
            svc_proba_test = clf["SVC"].predict_proba(X)
            xgb_proba_test = clf["XGB"].predict_proba(X)
            rf_proba_test = clf["RF"].predict_proba(X)

            X_stacked = np.column_stack((svc_proba_test, xgb_proba_test, rf_proba_test))
            proba.append(clf[mdl].predict_proba(X_stacked)[0][1])
        else:
            proba.append(clf[mdl].predict_proba(X)[0][1])

        pred.append((proba[-1] > st.session_state.mdl_thresh[mdl]) * 1)

    return pred, proba


def hard_vote(pred):
    hv = int(np.mean(pred).round(0))
    return "Autism Spectrum Disorder" if hv == 1 else "Typical Developed"


def save_scanpath_figs():
    # load precalculated faces & objects
    detected_faces = pickle.load(open(os.path.join("models", "faces.pickle"), "rb"))
    detected_objects = pickle.load(open(os.path.join("models", "objects.pickle"), "rb"))

    # filename
    id = st.session_state.eval_pat.split(":")[0]
    rec_date = ut.ugly_date(st.session_state.eval_meas)
    csv_file = os.path.join("recordings", f"id-{id}_{rec_date}.csv")

    # create folder if not there
    path_evaluation = os.path.join("evaluation", f"id-{id}_{rec_date}")
    if not os.path.exists(path_evaluation):
        os.makedirs(path_evaluation)

    # loop images
    sps = fct.load_scanpath(csv_file)
    for sp in sps:
        # img
        img_nr = sp["img"].iloc[0]

        # load image
        img = iio.imread(os.path.join("images", "stimuli", f"{img_nr}.png"))
        plt.figure(
            figsize=(round(img.shape[1] * 0.02), round(img.shape[0] * 0.02)),
            frameon=False,
        )
        ax = plt.gca()
        ax.set_axis_off()
        ax.imshow(img)

        # add faces
        faces = detected_faces[img_nr]
        for face in faces:
            left, top, w, h = face
            rect = patches.Rectangle(
                (left, top),
                w,
                h,
                linewidth=2,
                edgecolor="r",
                facecolor="none",
            )
            ax.add_patch(rect)

        # add objects
        objects = detected_objects[img_nr]
        for obj in objects:
            # name & score
            obj_name = obj["name"]
            bbox_coords = obj["bbox"]

            # add rectangle
            rect = patches.Rectangle(
                (bbox_coords[0], bbox_coords[1]),
                bbox_coords[2],
                bbox_coords[3],
                linewidth=2,
                edgecolor="orange",
                facecolor="none",
            )
            ax.add_patch(rect)

            # add label
            txt_name = f"{obj_name}"
            plt.text(
                bbox_coords[0],
                bbox_coords[1],
                txt_name,
                fontsize=6,
                backgroundcolor="orange",
                verticalalignment="top",
            )

        # style
        plt.ylim(img.shape[0] - 1, 0)
        plt.xlim(0, img.shape[1] - 1)
        plt.tight_layout

        # add saccades
        for r in range(1, sp.shape[0]):
            plt.plot(
                [sp.loc[sp["idx"] == r - 1]["x"], sp.loc[sp["idx"] == r]["x"]],
                [sp.loc[sp["idx"] == r - 1]["y"], sp.loc[sp["idx"] == r]["y"]],
                lw=6,
                c="#2c94ea",
            )

        # add fixations for individual plot
        s_min = 20
        s_max = 100
        sp["size"] = (sp["duration"] - np.min(sp["duration"])) / (
            np.max(sp["duration"]) - np.min(sp["duration"])
        ) * (s_max - s_min) + s_min
        sp["size"] = sp["size"].astype(int)

        for r in range(sp.shape[0]):
            ms = sp.loc[sp["idx"] == r]["size"].values
            plt.plot(
                sp.loc[sp["idx"] == r]["x"],
                sp.loc[sp["idx"] == r]["y"],
                "o",
                color="#2c94ea",
                mec="w",
                mew=1.5,
                ms=ms[0],
                alpha=0.8,
            )

        # save plot
        plt.savefig(
            os.path.join(path_evaluation, f"{img_nr}.png"),
            dpi=100,
            bbox_inches="tight",
            pad_inches=0,
        )

        # close plot
        plt.close()


# --- if script is run by it's own --------------------------------------------
if __name__ == "__main__":
    curdir = os.path.dirname(__file__)

    extract_features()
